# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
# ##### END GPL LICENSE BLOCK #####

import os
import traceback
import bpy
from . import shared
from .m3_materials import m3_material_get, m3_material_layer_get


# 节点名称前缀
M3_NODE_PREFIX = 'm3_layer:'

# Standard 材质层映射
STANDARD_LAYER_MAP = {
    'layer_diff': ('Base Color', False, 'Diffuse'),
    'layer_spec': ('Specular', True, 'Specular'),
    'layer_emis1': ('Emission', False, 'Emissive 1'),
    'layer_emis2': ('Emission2', False, 'Emissive 2'),
    'layer_norm': ('Normal', True, 'Normal'),
    'layer_ao': ('AO', True, 'AO'),
    'layer_alpha1': ('Alpha', True, 'Alpha'),
    'layer_height': ('Height', True, 'Height'),
    'layer_gloss': ('Roughness', True, 'Gloss'),
}


def find_texture_file(bitmap_path, texture_root):
    if not bitmap_path or not texture_root:
        return None
    rel_path = bitmap_path.replace('\\', os.sep).replace('/', os.sep).lstrip(os.sep)
    extensions = ['.dds', '.tga', '.png', '.jpg', '.tif', '.bmp']
    full_path = os.path.join(texture_root, rel_path)
    if os.path.isfile(full_path):
        return full_path
    base, ext = os.path.splitext(full_path)
    if ext:
        for new_ext in extensions:
            test_path = base + new_ext
            if os.path.isfile(test_path):
                return test_path
    for new_ext in extensions:
        test_path = full_path + new_ext
        if os.path.isfile(test_path):
            return test_path
    return None


def load_image(filepath):
    if not filepath:
        return None
    for img in bpy.data.images:
        try:
            if img.filepath and os.path.normpath(img.filepath) == os.path.normpath(filepath):
                return img
        except Exception:
            pass
    try:
        return bpy.data.images.load(filepath)
    except Exception:
        print("[M3] Failed to load: " + filepath)
        return None


def image_path_to_m3_path(filepath, texture_root):
    if not filepath or not texture_root:
        return ''
    try:
        abs_path = bpy.path.abspath(filepath)
        abs_path = os.path.normpath(abs_path)
        tex_root = os.path.normpath(texture_root)
        rel = os.path.relpath(abs_path, tex_root)
    except ValueError:
        rel = os.path.basename(filepath)
    return rel.replace(os.sep, '\\')


def get_principled_input(principled, name):
    """Safe access to Principled BSDF inputs, returns None if not found"""
    try:
        if name in principled.inputs:
            return principled.inputs[name]
    except Exception:
        pass
    return None


# ============================================================
# M3 -> Blender
# ============================================================

def create_standard_material(matref_name, mat_data, ob, texture_root):
    try:
        bl_mat_name = "M3_" + matref_name
        bl_mat = bpy.data.materials.get(bl_mat_name)
        if bl_mat:
            bl_mat.node_tree.nodes.clear()
        else:
            bl_mat = bpy.data.materials.new(name=bl_mat_name)

        bl_mat.use_nodes = True
        node_tree = bl_mat.node_tree
        node_tree.nodes.clear()
        bl_mat['m3_matref_name'] = matref_name

        output_node = node_tree.nodes.new('ShaderNodeOutputMaterial')
        output_node.location = (400, 0)
        principled = node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        principled.location = (0, 0)
        node_tree.links.new(principled.outputs['BSDF'], output_node.inputs['Surface'])

        spec_input = get_principled_input(principled, 'Specular')
        if spec_input:
            specularity = getattr(mat_data, 'specularity', 20.0)
            spec_input.default_value = min(specularity / 100.0, 1.0)

        x_offset = -600
        y_pos = 300
        emissive_nodes = []

        for layer_attr, (bsdf_input, non_color, desc) in STANDARD_LAYER_MAP.items():
            layer_handle = getattr(mat_data, layer_attr, '')
            if not layer_handle:
                continue

            layer = m3_material_layer_get(ob, layer_handle)
            if not layer:
                continue

            if layer.color_type != 'BITMAP' or not layer.color_bitmap:
                if layer.color_type == 'COLOR' and bsdf_input == 'Base Color':
                    bc = get_principled_input(principled, 'Base Color')
                    if bc:
                        bc.default_value = (layer.color_value[0], layer.color_value[1], layer.color_value[2], 1.0)
                continue

            tex_path = find_texture_file(layer.color_bitmap, texture_root)
            image = load_image(tex_path) if tex_path else None

            if not image:
                note = node_tree.nodes.new('NodeFrame')
                note.label = "[Missing] " + desc + ": " + layer.color_bitmap
                note.name = M3_NODE_PREFIX + layer_attr + "_missing"
                note.location = (x_offset, y_pos)
                y_pos -= 50
                continue

            tex_node = node_tree.nodes.new('ShaderNodeTexImage')
            tex_node.image = image
            tex_node.location = (x_offset, y_pos)
            tex_node.label = desc
            tex_node.name = M3_NODE_PREFIX + layer_attr
            tex_node.hide = True
            if non_color and image:
                try:
                    image.colorspace_settings.name = 'Non-Color'
                except Exception:
                    pass
            y_pos -= 80

            if bsdf_input == 'Normal':
                normal_map = node_tree.nodes.new('ShaderNodeNormalMap')
                normal_map.location = (x_offset + 300, tex_node.location[1])
                normal_map.hide = True
                node_tree.links.new(tex_node.outputs['Color'], normal_map.inputs['Color'])
                norm_input = get_principled_input(principled, 'Normal')
                if norm_input:
                    node_tree.links.new(normal_map.outputs['Normal'], norm_input)

            elif bsdf_input == 'Roughness':
                invert = node_tree.nodes.new('ShaderNodeInvert')
                invert.location = (x_offset + 300, tex_node.location[1])
                invert.hide = True
                node_tree.links.new(tex_node.outputs['Color'], invert.inputs['Color'])
                rough_input = get_principled_input(principled, 'Roughness')
                if rough_input:
                    node_tree.links.new(invert.outputs['Color'], rough_input)

            elif layer_attr in ('layer_emis1', 'layer_emis2'):
                emissive_nodes.append(tex_node)

            else:
                target = get_principled_input(principled, bsdf_input)
                if target:
                    node_tree.links.new(tex_node.outputs['Color'], target)

        # Emissive
        if emissive_nodes:
            emis_str = get_principled_input(principled, 'Emission Strength')
            if emis_str:
                emis_str.default_value = getattr(mat_data, 'hdr_emis', 1.0)

            # Blender 3.x = 'Emission', 4.x = 'Emission Color'
            emis_input = get_principled_input(principled, 'Emission Color')
            if not emis_input:
                emis_input = get_principled_input(principled, 'Emission')

            if emis_input and len(emissive_nodes) == 1:
                node_tree.links.new(emissive_nodes[0].outputs['Color'], emis_input)
            elif emis_input and len(emissive_nodes) > 1:
                mix_node = node_tree.nodes.new('ShaderNodeMixRGB')
                mix_node.blend_type = 'ADD'
                mix_node.location = (x_offset + 300, emissive_nodes[0].location[1])
                mix_node.inputs['Fac'].default_value = 1.0
                mix_node.hide = True
                node_tree.links.new(emissive_nodes[0].outputs['Color'], mix_node.inputs['Color1'])
                node_tree.links.new(emissive_nodes[1].outputs['Color'], mix_node.inputs['Color2'])
                node_tree.links.new(mix_node.outputs['Color'], emis_input)

        # Material settings
        blend_mode = getattr(mat_data, 'blend_mode', 'OPAQUE')
        if blend_mode != 'OPAQUE' and hasattr(bl_mat, 'blend_method'):
            try:
                bl_mat.blend_method = 'HASHED'
            except TypeError:
                try:
                    bl_mat.blend_method = 'ALPHA_HASHED'
                except Exception:
                    pass

        two_sided = getattr(mat_data, 'two_sided', False)
        bl_mat.use_backface_culling = not two_sided

        return bl_mat

    except Exception as e:
        print("[M3] Error creating material: " + str(e))
        traceback.print_exc()
        return None


def create_fallback_material(matref_name, mat_type_name):
    try:
        bl_mat_name = "M3_" + matref_name + " [" + mat_type_name + "]"
        bl_mat = bpy.data.materials.get(bl_mat_name)
        if not bl_mat:
            bl_mat = bpy.data.materials.new(name=bl_mat_name)
            bl_mat.use_nodes = True
            bl_mat['m3_matref_name'] = matref_name
            principled = bl_mat.node_tree.nodes.get('Principled BSDF')
            if principled:
                colors = {
                    'Displacement': (0.3, 0.3, 0.8, 1.0),
                    'Composite': (0.8, 0.8, 0.3, 1.0),
                    'Terrain': (0.4, 0.6, 0.2, 1.0),
                    'Volume': (0.5, 0.2, 0.8, 1.0),
                }
                bc = get_principled_input(principled, 'Base Color')
                if bc:
                    bc.default_value = colors.get(mat_type_name, (0.5, 0.5, 0.5, 1.0))
        return bl_mat
    except Exception as e:
        print("[M3] Error creating fallback material: " + str(e))
        return None


def generate_preview_materials(armature_ob, texture_root=""):
    if not armature_ob or armature_ob.type != 'ARMATURE':
        return None

    try:
        matrefs = armature_ob.m3_materialrefs
    except Exception:
        print("[M3] No m3_materialrefs on object")
        return None

    if len(matrefs) == 0:
        print("[M3] No materials found")
        return None

    mat_type_names = {
        'm3_materials_standard': 'Standard',
        'm3_materials_displacement': 'Displacement',
        'm3_materials_composite': 'Composite',
        'm3_materials_terrain': 'Terrain',
        'm3_materials_volume': 'Volume',
        'm3_materials_volumenoise': 'Volume Noise',
        'm3_materials_creep': 'Creep',
        'm3_materials_stb': 'Splat Terrain Bake',
        'm3_materials_reflection': 'Reflection',
        'm3_materials_lensflare': 'Lens Flare',
        'm3_materials_buffer': 'Buffer',
    }

    matref_to_bl_mat = {}

    print("[M3] Found " + str(len(matrefs)) + " material refs, texture_root=" + str(texture_root))

    for matref in matrefs:
        print("[M3]   matref: name=" + str(matref.name) + " type=" + str(matref.mat_type) + " handle=" + str(matref.mat_handle))
        mat = m3_material_get(matref)
        if not mat:
            print("[M3]   -> m3_material_get returned None, skipping")
            continue
        mat_type_name = mat_type_names.get(matref.mat_type, 'Unknown')
        print("[M3]   -> type=" + mat_type_name)
        if matref.mat_type == 'm3_materials_standard':
            bl_mat = create_standard_material(matref.name, mat, armature_ob, texture_root)
        else:
            bl_mat = create_fallback_material(matref.name, mat_type_name)
        if bl_mat:
            matref_to_bl_mat[matref.bl_handle] = bl_mat
            print("[M3]   -> Created: " + bl_mat.name)
        else:
            print("[M3]   -> Failed to create material")

    # Assign to meshes
    assigned = 0
    for child in armature_ob.children:
        if child.type != 'MESH':
            continue
        try:
            batches = child.m3_mesh_batches
        except Exception:
            continue
        if len(batches) == 0:
            continue

        child.data.materials.clear()
        for batch in batches:
            try:
                handle = batch.material.handle
            except Exception:
                continue
            bl_mat = matref_to_bl_mat.get(handle)
            if bl_mat and bl_mat.name not in child.data.materials:
                child.data.materials.append(bl_mat)
                assigned += 1

        if len(child.data.materials) == 0 and matref_to_bl_mat:
            child.data.materials.append(list(matref_to_bl_mat.values())[0])
            assigned += 1

    print("[M3] Done: " + str(len(matref_to_bl_mat)) + " materials, " + str(assigned) + " assignments")
    return matref_to_bl_mat


# ============================================================
# Blender -> M3
# ============================================================

def sync_material_to_m3(bl_mat, armature_ob, texture_root=""):
    if not bl_mat or not bl_mat.use_nodes:
        return 0, []

    matref_name = bl_mat.get('m3_matref_name', '')
    if not matref_name:
        return 0, []

    matref = None
    for mr in armature_ob.m3_materialrefs:
        if mr.name == matref_name:
            matref = mr
            break

    if not matref or matref.mat_type != 'm3_materials_standard':
        return 0, []

    mat_data = m3_material_get(matref)
    if not mat_data:
        return 0, []

    changes = []
    node_tree = bl_mat.node_tree

    for node in node_tree.nodes:
        if not node.name.startswith(M3_NODE_PREFIX):
            continue
        if node.type != 'TEX_IMAGE':
            continue

        layer_attr = node.name[len(M3_NODE_PREFIX):]
        layer_handle = getattr(mat_data, layer_attr, None)
        if layer_handle is None:
            continue

        layer = m3_material_layer_get(armature_ob, layer_handle)
        if not layer:
            continue

        if node.image:
            new_path = image_path_to_m3_path(node.image.filepath, texture_root)
            old_path = layer.color_bitmap
            if new_path and new_path != old_path:
                layer.color_bitmap = new_path
                changes.append(layer_attr + ": " + old_path + " -> " + new_path)
        else:
            if layer.color_bitmap:
                old_path = layer.color_bitmap
                layer.color_bitmap = ''
                changes.append(layer_attr + ": " + old_path + " -> (cleared)")

    # Read Principled params
    principled = None
    for node in node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            principled = node
            break

    if principled:
        try:
            spec_in = get_principled_input(principled, 'Specular')
            if spec_in:
                new_spec = spec_in.default_value * 100.0
                old_spec = mat_data.specularity
                if abs(new_spec - old_spec) > 0.01:
                    mat_data.specularity = new_spec
                    changes.append("Specularity: " + str(round(old_spec, 1)) + " -> " + str(round(new_spec, 1)))

            emis_in = get_principled_input(principled, 'Emission Strength')
            if emis_in:
                new_e = emis_in.default_value
                old_e = mat_data.hdr_emis
                if abs(new_e - old_e) > 0.01:
                    mat_data.hdr_emis = new_e
                    changes.append("Emission HDR: " + str(round(old_e, 2)) + " -> " + str(round(new_e, 2)))
        except Exception:
            pass

    try:
        old_ts = mat_data.two_sided
        new_ts = not bl_mat.use_backface_culling
        if new_ts != old_ts:
            mat_data.two_sided = new_ts
            changes.append("Two Sided: " + str(old_ts) + " -> " + str(new_ts))
    except Exception:
        pass

    return len(changes), changes


def sync_all_materials_to_m3(armature_ob, texture_root=""):
    total = 0
    details = []
    for bl_mat in bpy.data.materials:
        if not bl_mat.name.startswith('M3_'):
            continue
        c, d = sync_material_to_m3(bl_mat, armature_ob, texture_root)
        total += c
        details.extend(d)
    return total, details


# ============================================================
# Operators
# ============================================================

class M3MaterialPreviewGenerate(bpy.types.Operator):
    bl_idname = 'm3.material_preview_generate'
    bl_label = 'Generate Preview'
    bl_description = 'Generate Blender materials from M3 data'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.object
        if not ob or ob.type != 'ARMATURE':
            self.report({'ERROR'}, 'Select an armature')
            return {'CANCELLED'}

        texture_root = ''
        try:
            texture_root = ob.m3_texture_root
        except Exception:
            pass

        print("[M3] Generate Preview started, texture_root=" + str(texture_root))

        try:
            result = generate_preview_materials(ob, texture_root)
            if result:
                self.report({'INFO'}, 'Generated ' + str(len(result)) + ' materials')
            else:
                self.report({'WARNING'}, 'No materials generated - check console')
        except Exception as e:
            self.report({'ERROR'}, str(e))
            traceback.print_exc()

        return {'FINISHED'}


class M3MaterialPreviewSync(bpy.types.Operator):
    bl_idname = 'm3.material_preview_sync'
    bl_label = 'Sync to M3'
    bl_description = 'Write Blender material changes back to M3 data'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.object
        if not ob or ob.type != 'ARMATURE':
            self.report({'ERROR'}, 'Select an armature')
            return {'CANCELLED'}

        try:
            tex_root = ob.m3_texture_root if hasattr(ob, 'm3_texture_root') else ''
            count, details = sync_all_materials_to_m3(ob, tex_root)
            if count > 0:
                self.report({'INFO'}, 'Synced ' + str(count) + ' changes')
                for d in details:
                    print("[M3 Sync] " + d)
            else:
                self.report({'INFO'}, 'No changes detected')
        except Exception as e:
            self.report({'ERROR'}, str(e))
            traceback.print_exc()

        return {'FINISHED'}


class M3MaterialPreviewClear(bpy.types.Operator):
    bl_idname = 'm3.material_preview_clear'
    bl_label = 'Clear'
    bl_description = 'Remove all generated preview materials'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.object
        if not ob or ob.type != 'ARMATURE':
            self.report({'ERROR'}, 'Select an armature')
            return {'CANCELLED'}

        removed = 0
        for child in ob.children:
            if child.type == 'MESH':
                child.data.materials.clear()

        for mat in list(bpy.data.materials):
            if mat.name.startswith('M3_') and mat.users == 0:
                bpy.data.materials.remove(mat)
                removed += 1

        self.report({'INFO'}, 'Cleared ' + str(removed) + ' materials')
        return {'FINISHED'}


# ============================================================
# Panel
# ============================================================

class M3MaterialPreviewPanel(bpy.types.Panel):
    bl_idname = 'OBJECT_PT_M3_MATERIAL_PREVIEW'
    bl_label = 'M3 Material Preview'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'

    def draw(self, context):
        layout = self.layout
        ob = context.object

        try:
            mat_count = len(ob.m3_materialrefs)
        except Exception:
            mat_count = 0

        try:
            layer_count = len(ob.m3_materiallayers)
        except Exception:
            layer_count = 0

        mesh_count = sum(1 for child in ob.children if child.type == 'MESH')

        layout.label(text="Materials: " + str(mat_count) + "  Layers: " + str(layer_count) + "  Meshes: " + str(mesh_count))

        layout.separator()

        # Texture root path - editable directly on panel
        layout.prop(ob, 'm3_texture_root', text='Texture Root')

        layout.separator()

        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator('m3.material_preview_generate', icon='MATERIAL')
        row.operator('m3.material_preview_clear', icon='TRASH', text='Clear')

        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator('m3.material_preview_sync', icon='FILE_REFRESH')

        layout.separator()

        # Texture list
        try:
            if mat_count > 0 and layer_count > 0:
                box = layout.box()
                box.label(text="Texture Paths:", icon='IMAGE_DATA')
                shown = set()
                for layer in ob.m3_materiallayers:
                    if layer.color_bitmap and layer.color_bitmap not in shown:
                        shown.add(layer.color_bitmap)
                        box.label(text=layer.color_bitmap, icon='TEXTURE')
                if not shown:
                    box.label(text="(none)")
        except Exception:
            pass


# ============================================================
# Registration
# ============================================================

def register_props():
    bpy.types.Object.m3_texture_root = bpy.props.StringProperty(
        name="M3 Texture Root",
        subtype='DIR_PATH',
    )


classes = (
    M3MaterialPreviewGenerate,
    M3MaterialPreviewSync,
    M3MaterialPreviewClear,
    M3MaterialPreviewPanel,
)
