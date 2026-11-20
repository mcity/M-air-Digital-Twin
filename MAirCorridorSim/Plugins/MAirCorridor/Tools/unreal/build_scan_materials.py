"""build_scan_materials.py - the two materials the M-City scan is drawn with, built from nothing.

IN THE OPEN EDITOR, which is the easy way: the Output Log's command box, switched from Cmd to
Python, then

    exec(open(r"<project folder>/Plugins/MAirCorridor/Tools/unreal/build_scan_materials.py").read())

The materials are rebuilt in place and saved, and the scan redraws with them straight away.

HEADLESS, with the editor closed:

    UnrealEditor-Cmd.exe <project folder>/TheUniverse.uproject -run=pythonscript
        -script=<project folder>/Plugins/MAirCorridor/Tools/unreal/build_scan_materials.py
        "-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities" -unattended -nullrhi

BOTH PATHS MUST BE ABSOLUTE. The editor resolves a relative one against its own Binaries folder,
not the current one: given relative paths it either finds no project or no script. The Python
plugin is off in this project and the -EnablePlugins switch turns it on for this run only.

Set MAIRSCAN_DRY=1 to build both into throwaway materials and check them without saving anything.

  M_MCityScan     UNLIT, the default. The photographs already hold the light they were taken in,
                  and the scan is a procedural mesh with no distance field, so a lit material
                  gets direct sun and almost no sky light: everything not facing the sun renders
                  black. Unlit draws each photograph as it was taken, with EyeAdaptationInverse
                  cancelling the scene's exposure so it is neither black nor washed out whatever
                  units the level's sun is in. Brightness trims it.

  M_MCityScanLit  LIT, for when the scan should take the scene's sun and shadows. Matte and
                  non reflective (Roughness 1, Specular 0). Expect the dark faces described above
                  unless the level's sky lighting reaches procedural meshes.

Both have the texture parameter BaseColor, which the scan component binds each photograph to,
with the engine's DefaultDiffuse as its default so they compile on a machine without the scan.

EVERY CONNECTION IS CHECKED. An earlier version wired the photograph into EyeAdaptationInverse by
a pin name the engine does not use. Connecting by a wrong name does not raise; it returns False,
and nothing looked at it. The node, given no input, multiplies a constant 1 by the inverse
exposure, so the scan drew as pure white with no photograph in it at all. Now a connection that
does not take stops the build and names the pins that do exist, and the finished graph is read
back to prove the photograph reaches the output.
"""
import os

import unreal

MARK = "MAIRSCAN"
mel = unreal.MaterialEditingLibrary
DEFAULT_TEXTURE = "/Engine/EngineMaterials/DefaultDiffuse"
FOLDER = "/MAirCorridor/Materials"
DRY = os.environ.get("MAIRSCAN_DRY") == "1"


def say(text):
    unreal.log_warning("%s %s" % (MARK, text))
    print("%s %s" % (MARK, text))


def input_names(node):
    try:
        return [str(n) for n in mel.get_material_expression_input_names(node)]
    except Exception:
        return []


def link(source, source_output, target, target_input):
    """Connect two nodes, or stop and say which input names the target really has."""
    names = input_names(target)
    wanted = target_input
    if names and target_input not in names:
        # The pin is called by its property's display name; match ignoring case and spaces.
        squash = lambda s: s.replace(" ", "").lower()
        match = [n for n in names if squash(n) == squash(target_input)
                 or squash(n).startswith(squash(target_input))]
        if match:
            wanted = match[0]
    if not mel.connect_material_expressions(source, source_output, target, wanted):
        raise RuntimeError("could not connect %s to %s input %r; its inputs are %s" % (
            source.get_name(), target.get_name(), target_input, names))


def link_output(node, prop):
    if not mel.connect_material_property(node, "", prop):
        raise RuntimeError("could not connect %s to %s" % (node.get_name(), prop))


def fresh(name):
    if DRY:
        return unreal.new_object(unreal.Material, name="%s_DryRun" % name), None
    path = "%s/%s" % (FOLDER, name)
    # Load by path rather than asking the asset registry, which a headless run has not finished
    # scanning: asked, it says the asset is missing, and creating it then fails over the real file.
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous([FOLDER], True)
    material = unreal.load_asset(path)
    if material is not None:
        # One pass can leave nodes behind, so it repeats until the graph is empty.
        for _ in range(10):
            if mel.get_num_material_expressions(material) == 0:
                break
            mel.delete_all_material_expressions(material)
        return material, path
    return unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, FOLDER, unreal.Material, unreal.MaterialFactoryNew()), path


def scalar(material, name, value, x, y):
    node = mel.create_material_expression(material, unreal.MaterialExpressionScalarParameter, x, y)
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", value)
    node.set_editor_property("group", "Scan")
    return node


def photo_times_brightness(material):
    photo = mel.create_material_expression(material,
                                           unreal.MaterialExpressionTextureSampleParameter2D,
                                           -900, -80)
    photo.set_editor_property("parameter_name", "BaseColor")
    photo.set_editor_property("group", "Scan")
    photo.set_editor_property("texture", unreal.load_asset(DEFAULT_TEXTURE))
    photo.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
    brightness = scalar(material, "Brightness", 1.0, -900, 220)
    tint = mel.create_material_expression(material, unreal.MaterialExpressionMultiply, -550, -40)
    link(photo, "RGB", tint, "A")
    link(brightness, "", tint, "B")
    return photo, tint


def feeds(material, node):
    """The nodes plugged into each of node's inputs, None where nothing is."""
    try:
        return list(mel.get_inputs_for_material_expression(material, node))
    except Exception:
        return []


def finish(material, path, proof):
    mel.layout_material_expressions(material)
    mel.recompile_material(material)
    say("%s: %s" % (path or material.get_name(), proof))
    if path is None:
        return
    saved = unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    say("%s saved=%s nodes=%d textures=%s scalars=%s" % (
        path, saved, mel.get_num_material_expressions(material),
        [str(n) for n in mel.get_texture_parameter_names(material)],
        [str(n) for n in mel.get_scalar_parameter_names(material)]))


# ---- the default: unlit, the photograph as it was taken --------------------------------------
unlit, unlit_path = fresh("M_MCityScan")
unlit.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
unlit.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
unlit.set_editor_property("two_sided", True)
photo, tint = photo_times_brightness(unlit)

# EyeAdaptationInverse divides out the scene's exposure, so the photograph reaches the screen at
# its own brightness whatever units the level's sun is in. Its input is the property
# LightValueInput; link() finds the name the pin actually answers to.
compensate = mel.create_material_expression(unlit, unreal.MaterialExpressionEyeAdaptationInverse,
                                            -250, -40)
link(tint, "", compensate, "LightValue")
link_output(compensate, unreal.MaterialProperty.MP_EMISSIVE_COLOR)

# The proof: the photograph reaches the multiply, the multiply reaches the compensation, and the
# compensation is what the emissive output draws.
into_tint = feeds(unlit, tint)
into_comp = feeds(unlit, compensate)
if not into_comp or into_comp[0] != tint:
    raise RuntimeError("EyeAdaptationInverse is not fed by the photograph: %s" % into_comp)
if not into_tint or into_tint[0] != photo:
    raise RuntimeError("the multiply is not fed by the photograph: %s" % into_tint)
finish(unlit, unlit_path, "%s -> %s -> %s -> Emissive, read back from the graph" % (
    into_tint[0].get_name(), into_comp[0].get_name(), compensate.get_name()))

# ---- the alternative: lit, for when the scan should take the scene's sun and shadows --------
lit, lit_path = fresh("M_MCityScanLit")
lit.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
lit.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
lit.set_editor_property("two_sided", True)
photo, tint = photo_times_brightness(lit)
link_output(tint, unreal.MaterialProperty.MP_BASE_COLOR)
link_output(scalar(lit, "Roughness", 1.0, -550, 220), unreal.MaterialProperty.MP_ROUGHNESS)
link_output(scalar(lit, "Specular", 0.0, -550, 320), unreal.MaterialProperty.MP_SPECULAR)
finish(lit, lit_path, "photograph -> x Brightness -> Base Color, checked")
