"""recording.py - what a flight writes down, and the manifest that makes it a dataset.

Used by fly_mission.py; it is not run on its own.

WHY A DATASET AND NOT A PILE OF FILES. Two jobs need this recording, and neither survives a loose
folder of images:

  SIM TO REAL. Anything trained or validated on simulated flight needs the pixels, the depth, the
  labels and the aircraft state that produced them, each stamped with the clock the simulator used,
  and the camera geometry they came out of. So every stream carries an index keyed on the sim
  timestamp, depth stays sixteen bit, annotations sit beside the frames they describe, and each
  camera's size, field of view and mounting are written down.

  REAL TO SIM. A flight flown for real has to be comparable with the same route flown here, which
  means the recording must say exactly where its numbers sit in the world: the NED law, the
  projection, the landscape origin and the geodetic reference. manifest.json carries all of it, so
  a track can be turned back into longitude, latitude and metres above sea level by anything that
  reads JSON, without the landscape plan or the scene it was flown in.

WHAT GOES WHERE, inside one flight's folder:

  manifest.json                    everything below, described: streams, files, counts, geometry
  mission.json                     the mission as flown, copied
  track.jsonl                      the pose the simulator reported, and the deviation from the plan
  <sensor>_<stream>/               one folder per camera stream
      <sensor>.mp4                 the stream as video, when the pixels are eight bit
      000000.png                   lossless frames when asked for, sixteen bit for depth
      index.jsonl                  frame number, wall time, sim timestamp, size, encoding
      annotations.jsonl            object ids and bounding boxes, when the camera publishes them
  <sensor>_<stream>.jsonl          one file per data stream: IMU, GPS, lidar, radar, collisions
  <sensor>_<stream>.<field>.f32    bulk arrays, such as a lidar point cloud, as raw float32

CALLBACKS RUN ON THE CLIENT'S OWN THREADS. Everything here takes a lock, does the smallest amount of
work it can, and never raises into the caller: a recording that throws inside a subscription takes
the flight down with it.
"""
import array
import io
import json
import os
import shutil
import threading
import time

from toolpaths import HERE

# Camera streams are named after the image type they carry and all end this way. Everything else a
# robot config can declare (imu_kinematics, gps, lidar, radar_detections, battery, and the
# scene_camera_info metadata beside each image stream) is data.
IMAGE_SUFFIX = "_camera"

# A list this long inside a message is bulk data, not a field: a lidar point cloud is tens of
# thousands of floats and belongs in a binary file rather than in a line of JSON.
BULK = 48

# EVERY TEXT FILE HERE IS LINE BUFFERED. A flight gets stopped: by the button in the planner, by
# Ctrl-C, by the editor falling over. Python's default buffer is 8 KB, and a recording that loses
# its last 8 KB loses the end of the flight, silently. One line per write costs a syscall and is
# worth it. Binary bulk files keep their buffer, because a half written float32 block is worse than
# a missing one and the index in the line beside it says how much is real.
LINE_BUFFERED = 1

# How many frames to watch before deciding what rate to write a video at. A video file holds one
# number for its frame rate, and the honest value is the rate the frames actually arrived at, which
# nothing knows in advance: it depends on the camera's capture interval, how hard the scene is to
# render and what else the sim is doing. These few frames are held in memory while the rate is
# measured, so the number is small on purpose.
MEASURE_FRAMES = 6
MEASURE_SECONDS = 3.0


# The streams each kind of sensor publishes, and the stream each camera capture setting becomes.
# These mirror what the client builds in Drone.set_sensor_topics; they are here so a dry run can
# say what a flight would record without a simulator to ask. A live --list-capabilities always
# comes from the client itself and is the authority.
SENSOR_STREAMS = {"imu": ["imu_kinematics"], "gps": ["gps"], "airspeed": ["airspeed"],
                  "barometer": ["barometer"], "magnetometer": ["magnetometer"],
                  "lidar": ["lidar"], "radar": ["radar_detections", "radar_tracks"],
                  "distance-sensor": ["distance_sensor"], "battery": ["battery"]}
CAPTURE_STREAMS = {0: "scene_camera", 1: "depth_planar_camera", 2: "depth_camera",
                   3: "segmentation_camera", 4: "depth_vis_camera",
                   5: "disparity_normalized_camera", 6: "surface_normals_camera"}

# The streams that arrive as sixteen bit single channel pixels, which cannot go into a video. The
# real decision is made from the pixels themselves at runtime; this is only so a dry run can say
# what is going to happen.
SIXTEEN_BIT_STREAMS = ("depth_camera", "depth_planar_camera", "disparity_normalized_camera")

# What the client calls the robot's own topics.
ROBOT_STATE_STREAMS = ("actual_pose", "collision_info", "rotor_info")


def load_jsonc(path):
    """A Project AirSim config, which is JSON with line comments in it."""
    text = io.open(path, encoding="utf-8").read()
    out, in_string, escaped, i = [], False, False, 0
    while i < len(text):
        c = text[i]
        if in_string:
            out.append(c)
            if escaped:
                escaped = False
            elif c == chr(92):
                escaped = True
            elif c == '"':
                in_string = False
        elif c == '"':
            in_string = True
            out.append(c)
        elif c == "/" and text[i:i + 2] == "//":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        elif c == "/" and text[i:i + 2] == "/*":
            end = text.find("*/", i)
            i = len(text) if end < 0 else end + 2
            continue
        else:
            out.append(c)
        i += 1
    return json.loads("".join(out))


def streams_from_config(config):
    """{sensor: [streams]} as the client would build them from a robot config.

    Only enabled capture settings become streams, because that is what the client does, and each
    image stream brings a metadata stream of the same name with _info on the end."""
    sensors = {}
    for sensor in (config or {}).get("sensors", []):
        name, kind = sensor.get("id"), sensor.get("type")
        if not name:
            continue
        streams = []
        if kind == "camera":
            for capture in sensor.get("capture-settings", []):
                if not capture.get("capture-enabled"):
                    continue
                stream = CAPTURE_STREAMS.get(capture.get("image-type"))
                if stream:
                    streams += [stream, "%s_info" % stream]
        else:
            streams = list(SENSOR_STREAMS.get(kind, []))
        sensors[name] = sorted(streams)
    return sensors


def find_robot_config(scene_path, extra_dirs=(), robot=None):
    """The robot config a scene names, or robot (a file name) in its place, as a flight does.

    Returns (robot config, scene config, where it was read from), or (None, scene, why not)."""
    scene = load_jsonc(scene_path)
    actors = [a for a in scene.get("actors", []) if a.get("type") == "robot"]
    if not actors:
        return None, scene, "the scene declares no robot"
    named = robot or actors[0].get("robot-config")
    if isinstance(named, dict):
        return named, scene, scene_path
    if not named:
        return None, scene, "the robot names no config"
    for d in [os.path.dirname(os.path.abspath(scene_path))] + list(extra_dirs):
        candidate = os.path.join(d, named)
        if os.path.isfile(candidate):
            return load_jsonc(candidate), scene, candidate
    return None, scene, "%s was not found beside the scene or in the client's sim_config" % named


def stream_kind(stream):
    """"image" for a camera's pixels, "data" for everything else, including camera info."""
    return "image" if stream.endswith(IMAGE_SUFFIX) else "data"


def split_streams(sensors):
    """{sensor: [streams]} to ([(sensor, image stream)], [(sensor, data stream)])."""
    images, data = [], []
    for name in sorted(sensors):
        for stream in sorted(sensors[name]):
            (images if stream_kind(stream) == "image" else data).append((name, stream))
    return images, data


def human_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0 or unit == "TB":
            return "%.0f %s" % (n, unit) if unit == "B" else "%.1f %s" % (n, unit)
        n /= 1024.0


def tree_bytes(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


# ---------------------------------------------------------------------------------------------
# Streams
# ---------------------------------------------------------------------------------------------

def _as_bgr(img, cv2):
    """Whatever the camera sent, as the three channel frame a video writer takes.

    Chosen by channel count rather than by guessing from the dimensions: a GRAY8 image arrives as
    (height, width, 1), which is three dimensional but not colour, and OpenCV will quietly accept
    the wrong conversion for it."""
    channels = 1 if img.ndim == 2 else img.shape[2]
    if channels == 3:
        return img
    if channels == 1:
        return cv2.cvtColor(img.reshape(img.shape[0], img.shape[1]), cv2.COLOR_GRAY2BGR)
    if channels == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img[:, :, :3]


class ImageStream:
    """One camera stream, as video, as lossless frames, or both.

    DEPTH IS NOT VIDEO. A depth or disparity image arrives as sixteen bit single channel pixels;
    putting that through an eight bit video codec throws away the measurement that makes it useful.
    Those streams are always written as sixteen bit PNG frames and never as video, whatever was
    asked for, and the manifest says so."""

    def __init__(self, out_dir, sensor, stream, video=True, frames=False, fps=0.0, t0=None):
        self.dir = os.path.join(out_dir, "%s_%s" % (sensor, stream))
        os.makedirs(self.dir, exist_ok=True)
        self.sensor, self.stream = sensor, stream
        self.want_video, self.want_frames = video, frames
        # fps of 0 means measure it from the frames themselves; anything else is an instruction.
        self.asked_fps = float(fps or 0.0)
        self.fps = self.asked_fps
        self.pending = []              # frames held while the rate is being measured
        self.t0 = t0 or time.time()
        self.index = io.open(os.path.join(self.dir, "index.jsonl"), "w",
                             encoding="utf-8", newline="\n", buffering=LINE_BUFFERED)
        self.notes = []
        self.annotations = None
        self.writer = None
        self.video_path = None
        self.frame_ext = None
        self.count = 0
        self.dropped = 0
        self.width = self.height = 0
        self.encoding = ""
        self.sim_first = self.sim_last = None
        # The span of pixel values seen across the whole stream. A depth camera that is not
        # actually measuring the scene returns the same value everywhere, every frame, and
        # nothing else about the recording gives that away: the file size looks healthy and the
        # frames decode. Two numbers are enough to catch it.
        self.value_low = None
        self.value_high = None
        self.lock = threading.Lock()
        self._unpack = None
        self._cv2 = None
        self._np = None

    # ---- lazily, because importing the client costs a second ---------------------------------
    def _tools(self):
        if self._unpack is None:
            from projectairsim.utils import unpack_image
            self._unpack = unpack_image
            try:
                import cv2
                self._cv2 = cv2
            except ImportError:
                self._cv2 = False
                self.notes.append("opencv is not installed, so frames are numpy .npy arrays and "
                                  "no video was written")
            try:
                import numpy as np
                self._np = np
            except ImportError:
                self._np = False
        return self._unpack, self._cv2, self._np

    def frame(self, topic, message):
        try:
            self._write(message)
        except Exception as e:                      # never take the flight down over a frame
            with self.lock:
                self.dropped += 1
                if len(self.notes) < 4:
                    self.notes.append("a frame was dropped: %s" % e)

    def _write(self, message):
        unpack, cv2, np = self._tools()
        img = unpack(message)
        if img is None:
            return
        wall = round(time.time() - self.t0, 4)
        sim_ns = message.get("time_stamp")
        with self.lock:
            n = self.count
            self.height, self.width = int(img.shape[0]), int(img.shape[1])
            self.encoding = str(message.get("encoding", ""))
            if sim_ns is not None:
                self.sim_first = self.sim_first if self.sim_first is not None else sim_ns
                self.sim_last = sim_ns

            sixteen = getattr(img, "dtype", None) is not None and img.dtype.itemsize > 1
            try:
                low, high = float(img.min()), float(img.max())
                self.value_low = low if self.value_low is None else min(self.value_low, low)
                self.value_high = high if self.value_high is None else max(self.value_high, high)
            except (TypeError, ValueError):
                pass
            if sixteen and self.want_video and "no video" not in " ".join(self.notes):
                self.notes.append("sixteen bit pixels, so no video was written: a video codec "
                                  "would quantise the measurement to eight bits")

            name = None
            if cv2 and self.want_video and not sixteen:
                self._to_video(img, cv2, wall, sim_ns)
            if self.want_frames or sixteen or not cv2:
                if cv2:
                    name = "%06d.png" % n
                    cv2.imwrite(os.path.join(self.dir, name), img)
                elif np:
                    name = "%06d.npy" % n
                    np.save(os.path.join(self.dir, name), img)
                self.frame_ext = os.path.splitext(name)[1] if name else self.frame_ext

            row = {"n": n, "t": wall, "sim_ns": sim_ns, "w": self.width, "h": self.height,
                   "encoding": self.encoding}
            if name:
                row["file"] = name
            # WHERE THE CAMERA WAS WHEN IT TOOK THIS FRAME. The image message carries its own
            # pose, which is not the same as the aircraft's: the camera sits on a mount, and a
            # gimballed one moves independently. Without this a frame cannot be projected into
            # the world, which is most of what makes a recording useful afterwards.
            pose = self._pose(message)
            if pose:
                row["camera"] = pose
            self.index.write(json.dumps(row) + "\n")
            self.count += 1

            # Labels, when the camera config asks the sim for them. These are the supervision a
            # sim to real experiment is after, so they are kept whole rather than summarised.
            labels = message.get("annotations")
            if labels:
                if self.annotations is None:
                    self.annotations = io.open(os.path.join(self.dir, "annotations.jsonl"), "w",
                                               encoding="utf-8", newline="\n")
                self.annotations.write(json.dumps({"n": n, "t": wall, "sim_ns": sim_ns,
                                                   "annotations": labels}, default=str) + "\n")

    @staticmethod
    def _pose(message):
        """The camera pose the sim sends with each image, as NED metres and a quaternion."""
        try:
            keys = ("pos_x", "pos_y", "pos_z", "rot_w", "rot_x", "rot_y", "rot_z")
            if not all(k in message for k in keys):
                return None
            return {"ned_m": [float(message["pos_x"]), float(message["pos_y"]),
                              float(message["pos_z"])],
                    "quaternion_wxyz": [float(message["rot_w"]), float(message["rot_x"]),
                                        float(message["rot_y"]), float(message["rot_z"])]}
        except (TypeError, ValueError):
            return None

    def _to_video(self, img, cv2, wall, sim_ns):
        """Hold the first few frames, work out the rate they are arriving at, then write.

        Called with the lock held."""
        if self.writer is None and self.asked_fps <= 0.0:
            self.pending.append((img, wall, sim_ns))
            first_wall = self.pending[0][1]
            if len(self.pending) < MEASURE_FRAMES and wall - first_wall < MEASURE_SECONDS:
                return
            self.fps = self._measured_rate()
        if self.writer is None:
            self.fps = max(1.0, min(120.0, round(self.fps or 10.0, 1)))
            self.video_path = os.path.join(self.dir, "%s.mp4" % self.sensor)
            self.writer = cv2.VideoWriter(self.video_path, cv2.VideoWriter_fourcc(*"mp4v"),
                                          self.fps, (self.width, self.height))
            held, self.pending = self.pending, []
            for frame, _w, _s in held:
                self.writer.write(_as_bgr(frame, cv2))
            if held:
                return                      # the frame that triggered this was in the batch
        self.writer.write(_as_bgr(img, cv2))

    def _measured_rate(self):
        """Frames a second, from the simulator's clock where it gives one, else the wall clock."""
        if len(self.pending) < 2:
            return 10.0
        sims = [s for _i, _w, s in self.pending if s is not None]
        if len(sims) == len(self.pending):
            span = (sims[-1] - sims[0]) / 1e9
        else:
            span = self.pending[-1][1] - self.pending[0][1]
        if span <= 0.0:
            return 10.0
        return (len(self.pending) - 1) / span

    def rate_now(self):
        """The rate over everything recorded so far, which is the authority on timing."""
        if self.count < 2 or self.sim_first is None or self.sim_last is None:
            return None
        span = (self.sim_last - self.sim_first) / 1e9
        return None if span <= 0 else (self.count - 1) / span

    def close(self):
        with self.lock:
            # Anything still held while the rate was being measured belongs in the file.
            if self.pending and self.want_video:
                try:
                    import cv2
                    self.fps = max(1.0, min(120.0, round(self._measured_rate(), 1)))
                    self.video_path = os.path.join(self.dir, "%s.mp4" % self.sensor)
                    self.writer = cv2.VideoWriter(self.video_path,
                                                  cv2.VideoWriter_fourcc(*"mp4v"),
                                                  self.fps, (self.width, self.height))
                    for frame, _w, _s in self.pending:
                        self.writer.write(_as_bgr(frame, cv2))
                except Exception:
                    pass
                self.pending = []
            for f in (self.writer, self.index, self.annotations):
                try:
                    if f is self.writer:
                        f.release()
                    elif f is not None:
                        f.close()
                except Exception:
                    pass
            self.writer = None

    def constant(self):
        """True only when every pixel of every frame held the same value.

        THE THRESHOLD USED TO BE TWO PERCENT OF FULL SCALE, and that was wrong. This project's
        depth camera turned out to change by about one unit per metre, so a flight cruising
        within a 10 m band spans a dozen units of 65535 and would have been flagged as broken
        while it was measuring correctly. Measured, after the fact: centre depth rose steadily
        from 215 on the ground to 273 at 46 m. A range says nothing about whether a sensor works
        without knowing its scale, and the scale is exactly what is not known. A single value
        across a whole flight, though, is information about nothing."""
        return (self.count > 2 and self.value_low is not None and
                self.value_high - self.value_low < 1.0)

    def summary(self):
        if not self.count:
            return "%s/%s: nothing arrived" % (self.sensor, self.stream)
        if self.constant():
            return ("%s/%s: %d frames, EVERY PIXEL %.0f IN EVERY FRAME: the stream carries no "
                    "information" % (self.sensor, self.stream, self.count, self.value_low))
        what = []
        if self.video_path:
            what.append("video")
        if self.frame_ext:
            what.append("lossless %s" % self.frame_ext.lstrip("."))
        return "%s/%s: %d frames as %s, %dx%d, %s in %s" % (
            self.sensor, self.stream, self.count, " and ".join(what) or "nothing",
            self.width, self.height, human_bytes(tree_bytes(self.dir)), self.dir)

    def manifest(self):
        measured = self.rate_now()
        notes = list(self.notes)
        if self.constant():
            notes.append("every pixel of every frame was %.0f, so this stream carries no "
                         "information: check the sensor's mounting and whether this kind of "
                         "capture works in this scene" % self.value_low)
        if measured and self.fps and abs(measured - self.fps) / self.fps > 0.2:
            notes.append("the video says %.1f fps and the frames arrived at %.1f, so it plays at "
                         "%.2f times real speed; index.jsonl holds the true timing"
                         % (self.fps, measured, self.fps / measured))
        return {"sensor": self.sensor, "stream": self.stream, "kind": "image",
                "fps_written": self.fps if self.video_path else None,
                "fps_measured": None if measured is None else round(measured, 3),
                "folder": os.path.basename(self.dir),
                "video": os.path.basename(self.video_path) if self.video_path else None,
                "frames": self.frame_ext, "index": "index.jsonl",
                "index_line": '{"n": frame number, "t": seconds since the recording started, '
                              '"sim_ns": the simulator clock, "w"/"h"/"encoding": the pixels, '
                              '"file": the still if one was written, "camera": where the camera '
                              'was, in NED metres and a quaternion}',
                "annotations": "annotations.jsonl" if self.annotations is not None else None,
                "messages": self.count, "dropped": self.dropped,
                "width": self.width, "height": self.height, "encoding": self.encoding,
                "sim_ns_first": self.sim_first, "sim_ns_last": self.sim_last,
                "pixel_values_seen": None if self.value_low is None
                else [self.value_low, self.value_high],
                "bytes": tree_bytes(self.dir), "notes": notes}


class DataStream:
    """One non-image stream as JSON lines, with bulk arrays moved out to a binary file.

    A lidar message is a flat list of tens of thousands of floats. Written as JSON it is roughly
    twelve bytes a number and unreadable; written as float32 it is four, and a numpy memmap reads
    it in one call. So any array of BULK numbers or more (see the constant above) goes to
    <stream>.<field>.f32, and the line keeps {"f32": [offset, count]} in its place, measured in
    elements rather than bytes."""

    def __init__(self, out_dir, sensor, stream, hz=0.0, t0=None):
        self.path = os.path.join(out_dir, "%s_%s.jsonl" % (sensor, stream))
        self.file = io.open(self.path, "w", encoding="utf-8", newline="\n",
                            buffering=LINE_BUFFERED)
        self.sensor, self.stream = sensor, stream
        self.interval = (1.0 / hz) if hz and hz > 0 else 0.0
        self.t0 = t0 or time.time()
        self.last = 0.0
        self.count = 0
        self.skipped = 0
        self.empty_messages = 0        # messages whose list fields were all empty
        self.bulk = {}                 # field name to [open file, elements written]
        self.sim_first = self.sim_last = None
        self.lock = threading.Lock()

    def message(self, topic, message):
        try:
            self._write(message)
        except Exception:
            pass

    def _write(self, message):
        now = time.time()
        with self.lock:
            if self.interval and now - self.last < self.interval:
                self.skipped += 1
                return
            self.last = now
            body = message
            if isinstance(message, dict):
                body = {}
                measured = empty = 0
                for key, value in message.items():
                    # What a message measures, not its bookkeeping: a timestamp, the sensor's
                    # pose and a covariance (which a magnetometer, for one, leaves empty while
                    # reporting a perfectly good field) say nothing about whether it saw anything.
                    if key not in ("time_stamp", "pose") and "covariance" not in key:
                        measured += 1
                        if isinstance(value, (list, tuple)) and not value:
                            empty += 1
                    moved = self._offload(key, value)
                    body[key] = moved if moved is not None else value
                # A sensor can publish perfectly good messages that carry nothing: a lidar whose
                # rays hit nothing sends empty clouds, and the file looks healthy while holding no
                # measurements at all. Counted so the summary can say it out loud.
                if measured and empty == measured:
                    self.empty_messages += 1
                sim_ns = message.get("time_stamp")
                if sim_ns is not None:
                    self.sim_first = self.sim_first if self.sim_first is not None else sim_ns
                    self.sim_last = sim_ns
            else:
                sim_ns = None
            self.file.write(json.dumps({"t": round(now - self.t0, 4), "sim_ns": sim_ns,
                                        "msg": body}, default=str) + "\n")
            self.count += 1

    def _offload(self, key, value):
        """A long numeric list to a binary file, returning what to put in the line instead.

        Whole numbers are kept as int32, because a segmentation id or a laser index is a label
        rather than a measurement and should come back exactly as it went in."""
        if not isinstance(value, (list, tuple)) or len(value) < BULK:
            return None
        block = None
        if all(isinstance(v, int) and not isinstance(v, bool) for v in value):
            try:
                block = array.array("i", value)
            except (TypeError, ValueError, OverflowError):
                block = None
        if block is None:
            try:
                block = array.array("f", value)
            except (TypeError, ValueError, OverflowError):
                return None                          # not numbers: leave it in the line
        kind = "i32" if block.typecode == "i" else "f32"
        entry = self.bulk.get(key)
        if entry is None:
            path = "%s.%s.%s" % (os.path.splitext(self.path)[0], key, kind)
            entry = [io.open(path, "wb"), 0, path, kind]
            self.bulk[key] = entry
        elif entry[3] != kind:
            return None             # the stream changed its mind: keep this one in the line
        entry[0].write(block.tobytes())
        offset = entry[1]
        entry[1] += len(block)
        return {kind: [offset, len(block)]}

    def close(self):
        with self.lock:
            for entry in self.bulk.values():
                try:
                    entry[0].close()
                except Exception:
                    pass
            try:
                self.file.close()
            except Exception:
                pass

    def summary(self):
        if not self.count:
            return "%s/%s: nothing arrived" % (self.sensor, self.stream)
        if self.empty_messages == self.count and not self.bulk:
            return ("%s/%s: %d messages, EVERY ONE EMPTY: the sensor published but measured "
                    "nothing. Check its settings and what it is pointed at."
                    % (self.sensor, self.stream, self.count))
        extra = ""
        if self.bulk:
            extra = ", plus %s of %s" % (
                human_bytes(sum(tree_bytes(e[2]) for e in self.bulk.values())),
                " and ".join(sorted(self.bulk)))
        return "%s/%s: %d messages, %s%s" % (self.sensor, self.stream, self.count,
                                             human_bytes(tree_bytes(self.path)), extra)

    def manifest(self):
        return {"sensor": self.sensor, "stream": self.stream, "kind": "data",
                "file": os.path.basename(self.path), "messages": self.count,
                "messages_with_nothing_in_them": self.empty_messages,
                "rate_limited_out": self.skipped,
                "rate_cap_hz": None if not self.interval else round(1.0 / self.interval, 3),
                "sim_ns_first": self.sim_first, "sim_ns_last": self.sim_last,
                "bulk": {k: {"file": os.path.basename(e[2]),
                             "dtype": "int32" if e[3] == "i32" else "float32",
                             "elements": e[1],
                             "layout": "every message appended in order; each line gives "
                                       "[offset, count] in elements"}
                         for k, e in sorted(self.bulk.items())},
                "line": '{"t": seconds since the recording started, "sim_ns": the simulator '
                        'clock, "msg": the message as published}',
                "bytes": tree_bytes(self.path) + sum(tree_bytes(e[2])
                                                     for e in self.bulk.values())}


class TrackStream:
    """The pose the simulator reports, and how far it is from the planned route.

    Callbacks arrive on the client's threads and must return quickly, so this measures, appends a
    line, and rate limits only what it prints. DEVIATION IS MEASURED TO THE LINE, not to the next
    waypoint: a drone cutting a corner is where it should be, one forty metres to the side of a leg
    is not, even halfway between two waypoints."""

    def __init__(self, path, planned, deviation_fn, print_hz=4.0, t0=None, observer=None):
        self.file = io.open(path, "w", encoding="utf-8", newline="\n",
                            buffering=LINE_BUFFERED)
        self.path = path
        self.planned = planned
        self.deviation = deviation_fn
        # Something else that wants every position, and has a verdict to add to the row: the
        # operation, which checks conformance against the declared volumes. Kept as a callable so
        # this module needs to know nothing about airspace.
        self.observer = observer
        self.lock = threading.Lock()
        self.print_interval = 1.0 / max(0.1, print_hz)
        self.last_print = 0.0
        self.t0 = t0 or time.time()
        self.samples = 0
        self.worst = 0.0
        self.total = 0.0
        self.leg = 0
        # The first and last sample on both clocks: the simulator's and the wall's. Their ratio
        # is how fast the simulation actually ran, which is the first number to look at when a
        # flight feels slow.
        self.first_clocks = None
        self.last_clocks = None

    def pose(self, topic, message):
        try:
            p = message["position"]
            point = (float(p["x"]), float(p["y"]), float(p["z"]))
        except (KeyError, TypeError, ValueError):
            return
        dev, leg = self.deviation(self.planned, point)
        now = time.time()
        row = {"t": round(now - self.t0, 3), "north": point[0], "east": point[1],
               "down": point[2], "deviation": None if dev is None else round(dev, 3), "leg": leg,
               "sim_ns": message.get("time_stamp")}
        if self.observer is not None:
            try:
                row["conformance"] = self.observer(*point, sim_ns=row["sim_ns"])
            except Exception as e:             # a checker that throws must not stop the track
                row["conformance"] = {"ok": None, "reason": "check failed: %s" % e}
        with self.lock:
            self.samples += 1
            if row["sim_ns"] is not None:
                clocks = (now, row["sim_ns"])
                self.first_clocks = self.first_clocks or clocks
                self.last_clocks = clocks
            if dev is not None:
                self.worst = max(self.worst, dev)
                self.total += dev
                self.leg = leg
            if self.file.closed:
                # A pose already on its way when the flight ended; the track is written.
                return
            self.file.write(json.dumps(row) + "\n")
            due = now - self.last_print >= self.print_interval
            if due:
                self.last_print = now
        if due:
            # The planner reads these lines to draw the drone and its deviation as it flies.
            print("TRACK " + json.dumps(row), flush=True)

    def sim_speed(self):
        """Simulated seconds per real second over the flight, or None when it cannot be told."""
        with self.lock:
            if not self.first_clocks or not self.last_clocks:
                return None
            wall = self.last_clocks[0] - self.first_clocks[0]
            sim = (self.last_clocks[1] - self.first_clocks[1]) / 1e9
        return None if wall < 1.0 else sim / wall

    def summary(self):
        with self.lock:
            if not self.samples:
                return "no pose was reported, so nothing was tracked"
            return ("%d samples, worst deviation %.1f m, average %.1f m, written to %s"
                    % (self.samples, self.worst, self.total / self.samples, self.path))

    def manifest(self):
        with self.lock:
            return {"file": os.path.basename(self.path), "samples": self.samples,
                    "worst_deviation_m": round(self.worst, 3),
                    "average_deviation_m": round(self.total / self.samples, 3)
                    if self.samples else None,
                    "line": '{"t": seconds, "north": m, "east": m, "down": m, '
                            '"deviation": m from the planned line, "leg": which leg, '
                            '"sim_ns": the simulator clock}',
                    "bytes": tree_bytes(self.path)}


# ---------------------------------------------------------------------------------------------
# The dataset
# ---------------------------------------------------------------------------------------------

SEGMENTATION_TABLE = os.path.join(HERE, "segmentation.json")


def segmentation_classes():
    """The level's segmentation classes, each with the colour it has in the segmentation image.

    The ids are written into the level's components (unreal/label_segmentation.py); the colour of
    an id is Project AirSim's palette entry for it, which is how a segmentation frame is read back
    into classes."""
    try:
        with io.open(SEGMENTATION_TABLE, encoding="utf-8") as f:
            classes = json.load(f)["classes"]
    except (OSError, ValueError, KeyError):
        return None
    # The colour is Project AirSim's palette entry, in the order it lists it. Measured on a recorded
    # segmentation video decoded to RGB: pixels sit a median 4 units from the entry as listed (video
    # compression) and 34 from it reversed. (The client's own data collection helper reverses a
    # pixel before looking it up, for images that reach it the other way round.)
    try:
        from projectairsim.image_utils import SEGMENTATION_PALLETE as palette
    except Exception:
        palette = None
    out = {}
    for name, c in classes.items():
        row = {"id": c["id"], "what": c.get("what")}
        if palette is not None and 0 <= c["id"] < len(palette):
            row["rgb"] = [int(v) for v in palette[c["id"]]]
        out[name] = row
    return out


def label_drone(world, drone_name):
    """Give the flown aircraft its segmentation class. The scene configs turn Project AirSim's own
    labelling off so it cannot overwrite the level's, which leaves the drone, spawned by the scene
    rather than placed in the level, for this to do. Returns the id, or None."""
    classes = segmentation_classes() or {}
    drone = classes.get("drone")
    if not drone:
        return None
    try:
        ok = world.set_segmentation_id_by_name(drone_name, drone["id"], False, True)
    except Exception:
        return None
    return drone["id"] if ok else None


def robot_config(world, drone_name):
    """The drone's own robot config, straight out of the scene the sim loaded.

    Worth the trouble because drone.sensors lists every sensor the config DECLARES, including the
    ones switched off with "enabled": false, and those publish nothing at all. Recording them would
    write empty files and look like a fault."""
    try:
        scene = world.get_configuration()
    except Exception:
        return {}, {}
    for actor in scene.get("actors", []):
        if actor.get("name") == drone_name:
            return actor.get("robot-config") or {}, scene
    return {}, scene


def sensor_facts(config):
    """{sensor: {"type", "enabled", "cameras": [...], "origin": {...}}} from a robot config."""
    facts = {}
    for sensor in (config or {}).get("sensors", []):
        name = sensor.get("id")
        if not name:
            continue
        fact = {"type": sensor.get("type"), "enabled": bool(sensor.get("enabled", True)),
                "origin": sensor.get("origin")}
        if sensor.get("type") == "camera":
            fact["capture_interval_s"] = sensor.get("capture-interval")
            fact["cameras"] = [
                {"image_type": c.get("image-type"), "capture_enabled": c.get("capture-enabled"),
                 "streaming_enabled": c.get("streaming-enabled"),
                 "width": c.get("width"), "height": c.get("height"),
                 "fov_degrees": c.get("fov-degrees"),
                 "pixels_as_float": c.get("pixels-as-float"), "compress": c.get("compress")}
                for c in sensor.get("capture-settings", [])]
            fact["gimbal"] = sensor.get("gimbal")
        facts[name] = fact
    return facts


class Dataset:
    """One flight's folder: the streams in it, and the manifest that describes them."""

    def __init__(self, out_dir, mission, mission_path, terrain):
        self.dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.mission = mission
        self.mission_path = mission_path
        self.terrain = terrain
        self.t0 = time.time()
        self.images = []
        self.data = []
        self.track = None
        self.taken = set()
        self.notes = []
        self.scene_config = {}
        self.robot = {}
        try:
            shutil.copy2(mission_path, os.path.join(out_dir, "mission.json"))
        except Exception as e:
            self.notes.append("the mission could not be copied in: %s" % e)

    # ---- adding streams ----------------------------------------------------------------------
    def image(self, sensor, stream, video=True, frames=False, fps=10.0):
        if (sensor, stream) in self.taken:
            return None
        self.taken.add((sensor, stream))
        s = ImageStream(self.dir, sensor, stream, video=video, frames=frames, fps=fps, t0=self.t0)
        self.images.append(s)
        return s

    def data_stream(self, sensor, stream, hz=0.0):
        if (sensor, stream) in self.taken:
            return None
        self.taken.add((sensor, stream))
        s = DataStream(self.dir, sensor, stream, hz=hz, t0=self.t0)
        self.data.append(s)
        return s

    def tracker(self, planned, deviation_fn, print_hz=4.0, observer=None):
        self.track = TrackStream(os.path.join(self.dir, "track.jsonl"), planned, deviation_fn,
                                 print_hz=print_hz, t0=self.t0, observer=observer)
        return self.track

    @property
    def streams(self):
        return list(self.images) + list(self.data)

    # ---- the frames, written down so nothing has to guess them -------------------------------
    def frames_block(self):
        """Exactly how to get from what was recorded back to the world, and the other way.

        This is the part that makes a real flight comparable with a simulated one. Everything here
        comes from the landscape plan the mission was drawn against, so a reader needs this file and
        nothing else to turn north, east and down into longitude, latitude and metres above sea
        level."""
        t = self.terrain
        block = {"ned": "north = unreal_x_cm / 100, east = unreal_y_cm / 100, "
                        "down = -unreal_z_cm / 100",
                 "ned_is_not_true_north": "the NED axes follow the Unreal level's axes, which is "
                                          "what the scene config sets up; grid north of the "
                                          "projection below, not magnetic or true north",
                 "plan": getattr(t, "path", None)}
        if t is None:
            return block
        try:
            seg = t.segments[0]
            origin = seg.get("projected_origin") or t.plan.get("utm_origin")
            loc = t.location_cm(seg) if hasattr(t, "location_cm") else seg.get(
                "actor_location_cm", t.plan.get("actor_location_cm", [0.0, 0.0, 0.0]))
            block.update({
                "projection": "EPSG:%d" % t.epsg,
                "projected_origin_m": [float(origin[0]), float(origin[1])],
                "origin_meaning": "easting and northing of the landscape's north west corner; "
                                  "unreal_x_cm = (easting - origin[0]) * 100, "
                                  "unreal_y_cm = (origin[1] - northing) * 100",
                "quad_metres": t.quad,
                "actor_location_cm": [float(v) for v in loc],
                "actor_location_from": getattr(t, "placement_source", None),
                "elev_mid_m": float(seg.get("elev_mid_m", t.plan["elev_mid_m"])),
                "elevation": "metres_above_sea_level = (-down * 100 - actor_location_cm[2]) / 100 "
                             "+ elev_mid_m",
                "extent_lonlat": list(t.extent_lonlat()),
            })
        except Exception as e:
            block["incomplete"] = "the landscape plan did not give the full frame: %s" % e
        home = (self.scene_config or {}).get("home-geo-point")
        if home:
            block["home_geo_point"] = home
        # Every height in a recording is NAVD88 orthometric metres, because that is what the
        # landscape is built in. A reader comparing it with GPS needs the separation to get back
        # to the ellipsoid, so the model and its value over the landscape are written down.
        block["vertical_datum"] = "NAVD88 orthometric metres (USGS 3DEP), the landscape's own"
        try:
            import geoid as geoid_module
            model = geoid_module.Geoid.default()
            west, south, east, north = t.extent_lonlat()
            lon, lat = (west + east) / 2.0, (south + north) / 2.0
            block["geoid"] = {"model": model.model, "relates": model.relates,
                              "separation_m_at_centre": round(model.separation(lon, lat), 3),
                              "to_ellipsoid": "wgs84_height = navd88_height + separation"}
        except Exception as e:
            block["geoid"] = {"model": None,
                              "note": "no geoid model installed when this was recorded (%s); "
                                      "about -34 m around Ann Arbor" % e}
        return block

    # ---- how fast it ran ----------------------------------------------------------------------
    def performance(self):
        """How fast the flight ran, and which cameras could not keep up.

        THE MEASUREMENT THAT FOUND THE SLOWDOWN. Every stream carries the simulator's clock and the
        wall clock, so the recording itself says how fast things went. Flown with every sensor on,
        the simulation ran at 0.87 of real time and cameras asking for 10 and 33 frames a second
        delivered 1.7 to 2.8; the cause was the number of full scene renders each frame asked for.
        Rates are in simulated time, which is what a dataset is consumed in."""
        facts = sensor_facts(self.robot)
        out = {"sim_speed": None, "cameras": [], "verdict": []}
        if self.track is not None:
            speed = self.track.sim_speed()
            if speed is not None:
                out["sim_speed"] = round(speed, 3)
                out["verdict"].append("the simulation ran at %.2f of real time%s" % (
                    speed, "" if speed >= 0.97 else ": it is falling behind"))
        for stream in self.images:
            got = stream.rate_now()
            interval = (facts.get(stream.sensor) or {}).get("capture_interval_s")
            asked = (1.0 / interval) if interval else None
            row = {"sensor": stream.sensor, "stream": stream.stream,
                   "asked_hz": None if asked is None else round(asked, 2),
                   "got_hz": None if got is None else round(got, 2),
                   "share": None if (got is None or not asked) else round(got / asked, 3)}
            out["cameras"].append(row)
        short = [c for c in out["cameras"] if c["share"] is not None and c["share"] < 0.8]
        if short:
            worst = min(short, key=lambda c: c["share"])
            out["verdict"].append(
                "%d camera stream(s) fell short; worst %s/%s delivered %.1f of %.0f frames a second "
                "(%.0f%%). Each capture is a full render of the scene: fewer or smaller captures "
                "are what make it faster" % (len(short), worst["sensor"], worst["stream"],
                                             worst["got_hz"], worst["asked_hz"],
                                             100.0 * worst["share"]))
        elif out["cameras"]:
            out["verdict"].append("every camera kept up with the rate it asked for")
        return out

    # ---- the manifest ------------------------------------------------------------------------
    def write_manifest(self, extra=None):
        streams = [s.manifest() for s in self.streams]
        total = sum(s.get("bytes") or 0 for s in streams)
        if self.track:
            total += self.track.manifest().get("bytes") or 0
        facts = sensor_facts(self.robot)
        off = sorted(n for n, f in facts.items() if not f.get("enabled", True))
        manifest = {
            "format": "maircorridor-flight/1",
            "what": "one flight recorded from Project AirSim: the route flown, the aircraft state, "
                    "and every camera and sensor stream that was switched on",
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "duration_s": round(time.time() - self.t0, 2),
            "tool": "fly_mission.py",
            "mission": {"name": getattr(self.mission, "name", None),
                        "file": "mission.json",
                        "source": os.path.abspath(self.mission_path),
                        "drone": getattr(self.mission, "drone", None),
                        "scene": getattr(self.mission, "scene", None),
                        "yaw_mode": getattr(self.mission, "yaw_mode", None),
                        "waypoints": len(getattr(self.mission, "waypoints", []) or [])},
            "frames": self.frames_block(),
            "sensors": facts,
            "sensors_declared_but_off": off,
            "streams": streams,
            "track": self.track.manifest() if self.track else None,
            "performance": self.performance(),
            "segmentation_classes": segmentation_classes(),
            "bytes": total,
            "notes": self.notes,
        }
        if extra:
            manifest.update(extra)
        path = os.path.join(self.dir, "manifest.json")
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(manifest, f, indent=2, default=str)
            f.write("\n")
        return path, total

    def close(self, extra=None):
        """Shut every stream, print what was written, and leave the manifest behind."""
        lines = []
        for s in self.streams:
            s.close()
            lines.append(s.summary())
        if self.track:
            try:
                with self.track.lock:
                    self.track.file.close()
            except Exception:
                pass
            lines.append(self.track.summary())
        path, total = self.write_manifest(extra)
        for line in self.performance()["verdict"]:
            lines.append("speed: %s" % line)
        lines.append("%s of recording in %s" % (human_bytes(total), self.dir))
        lines.append("described by %s" % path)
        return lines


def read_manifest(path):
    """A flight's manifest, given the folder or the file itself."""
    if os.path.isdir(path):
        path = os.path.join(path, "manifest.json")
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def lonlat_from_frames(frames, north, east):
    """Longitude and latitude from NED, using only what a manifest's "frames" block says.

    The point of writing the frame down: this works from the manifest alone, so a recording stays
    readable without the landscape plan, the scene, or this repository."""
    from rasterio.warp import transform as reproject_points
    origin = frames["projected_origin_m"]
    easting = origin[0] + north
    northing = origin[1] - east
    xs, ys = reproject_points(frames["projection"], "EPSG:4326", [easting], [northing])
    return xs[0], ys[0]


def elevation_from_frames(frames, down):
    """Metres above sea level from NED down, from the manifest alone."""
    return (-down * 100.0 - frames["actor_location_cm"][2]) / 100.0 + frames["elev_mid_m"]
