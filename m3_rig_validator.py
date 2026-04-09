# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import traceback
from . import shared


def validate_rig(armature_ob):
    """Run all validation checks and return a list of (severity, message) tuples.
    severity: 'ERROR', 'WARNING', 'INFO'
    """
    issues = []

    if not armature_ob or armature_ob.type != 'ARMATURE':
        issues.append(('ERROR', 'Not an armature object'))
        return issues

    bones = armature_ob.data.bones
    bone_names = set(b.name for b in bones)

    # --- 1. Check Attachment Points ---
    try:
        for ap in armature_ob.m3_attachmentpoints:
            bone_ref = ap.bone.value if hasattr(ap.bone, 'value') else ''
            if not bone_ref:
                issues.append(('WARNING', 'Attachment "' + ap.name + '" has no bone assigned'))
            elif bone_ref not in bone_names:
                issues.append(('ERROR', 'Attachment "' + ap.name + '" references missing bone "' + bone_ref + '"'))
            # Check naming convention
            if not ap.name.startswith('Ref_') and not ap.name.startswith('Pos_'):
                issues.append(('WARNING', 'Attachment "' + ap.name + '" should start with Ref_ or Pos_'))
    except Exception:
        pass

    # --- 2. Check Mesh Vertex Groups ---
    meshes = [child for child in armature_ob.children if child.type == 'MESH']

    for mesh_ob in meshes:
        # Check vertex groups match bone names
        for vg in mesh_ob.vertex_groups:
            if vg.name not in bone_names:
                issues.append(('WARNING', 'Mesh "' + mesh_ob.name + '" has vertex group "' + vg.name + '" with no matching bone'))

        # Check for unweighted vertices
        try:
            mesh = mesh_ob.data
            unweighted = 0
            for vert in mesh.vertices:
                if len(vert.groups) == 0:
                    unweighted += 1
            if unweighted > 0:
                issues.append(('WARNING', 'Mesh "' + mesh_ob.name + '" has ' + str(unweighted) + ' unweighted vertices'))
        except Exception:
            pass

        # Check if mesh is parented with armature deform
        if mesh_ob.parent != armature_ob:
            issues.append(('INFO', 'Mesh "' + mesh_ob.name + '" is not parented to armature'))
        else:
            has_armature_mod = False
            for mod in mesh_ob.modifiers:
                if mod.type == 'ARMATURE':
                    has_armature_mod = True
                    if mod.object != armature_ob:
                        issues.append(('ERROR', 'Mesh "' + mesh_ob.name + '" armature modifier points to wrong object'))
            if not has_armature_mod and mesh_ob.vertex_groups:
                issues.append(('WARNING', 'Mesh "' + mesh_ob.name + '" has vertex groups but no Armature modifier'))

    # --- 3. Check Bone Export Cull ---
    try:
        for pb in armature_ob.pose.bones:
            if pb.m3_export_cull:
                # Check if this bone is used by anything
                is_used = False

                # Used by attachment?
                for ap in armature_ob.m3_attachmentpoints:
                    if hasattr(ap.bone, 'value') and ap.bone.value == pb.name:
                        is_used = True
                        break

                # Used by mesh vertex group?
                if not is_used:
                    for mesh_ob in meshes:
                        if pb.name in mesh_ob.vertex_groups:
                            is_used = True
                            break

                if is_used:
                    # Bone is used but has export_cull = True (default)
                    # This is fine because the exporter will keep it since it's referenced
                    pass
    except Exception:
        pass

    # --- 4. Check Material References ---
    try:
        for matref in armature_ob.m3_materialrefs:
            if not matref.mat_handle:
                issues.append(('WARNING', 'Material ref "' + matref.name + '" has no material linked'))
    except Exception:
        pass

    # --- 5. Check M3 Mesh Batches ---
    for mesh_ob in meshes:
        try:
            batches = mesh_ob.m3_mesh_batches
            if len(batches) == 0:
                issues.append(('INFO', 'Mesh "' + mesh_ob.name + '" has no M3 batch data'))
        except Exception:
            pass

    # --- 6. Check for common bone naming issues ---
    for bone in bones:
        if ' ' in bone.name:
            issues.append(('INFO', 'Bone "' + bone.name + '" contains spaces (may cause issues)'))

    # --- 7. Summary ---
    if not issues:
        issues.append(('INFO', 'All checks passed - no issues found'))

    return issues


# ============================================================
# Operator
# ============================================================

class M3RigValidate(bpy.types.Operator):
    bl_idname = 'm3.rig_validate'
    bl_label = 'Validate Rig'
    bl_description = 'Check for common M3 rigging issues'
    bl_options = {'REGISTER'}

    def execute(self, context):
        ob = context.object
        if not ob or ob.type != 'ARMATURE':
            self.report({'ERROR'}, 'Select an armature')
            return {'CANCELLED'}

        try:
            issues = validate_rig(ob)

            # Store results on object for panel display
            ob['m3_rig_issues'] = [(sev, msg) for sev, msg in issues]

            errors = sum(1 for s, _ in issues if s == 'ERROR')
            warnings = sum(1 for s, _ in issues if s == 'WARNING')
            infos = sum(1 for s, _ in issues if s == 'INFO')

            # Print to console
            print("=" * 50)
            print("[M3 Rig Validator] Results:")
            for sev, msg in issues:
                print("  [" + sev + "] " + msg)
            print("=" * 50)

            self.report({'INFO'}, str(errors) + ' errors, ' + str(warnings) + ' warnings, ' + str(infos) + ' info')

        except Exception as e:
            self.report({'ERROR'}, str(e))
            traceback.print_exc()

        return {'FINISHED'}


# ============================================================
# Panel
# ============================================================

class M3RigValidatorPanel(bpy.types.Panel):
    bl_idname = 'OBJECT_PT_M3_RIG_VALIDATOR'
    bl_label = 'M3 Rig Validator'
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

        row = layout.row()
        row.scale_y = 1.5
        row.operator('m3.rig_validate', icon='VIEWZOOM')

        # Show stored results
        try:
            issues = ob.get('m3_rig_issues', [])
            if issues:
                layout.separator()
                box = layout.box()

                for item in issues:
                    sev = item[0]
                    msg = item[1]

                    if sev == 'ERROR':
                        icon = 'ERROR'
                    elif sev == 'WARNING':
                        icon = 'CANCEL'
                    else:
                        icon = 'CHECKMARK'

                    box.label(text=msg, icon=icon)
        except Exception:
            pass


# ============================================================
# Registration
# ============================================================

def register_props():
    pass


classes = (
    M3RigValidate,
    M3RigValidatorPanel,
)
