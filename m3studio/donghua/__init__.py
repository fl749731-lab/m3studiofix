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
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

"""
M3 动画工作站 (M3 Animation Workstation)

方便 M3 模型动画制作的一站式工具集，提供：
- 快速关键帧操作（批量插帧/删帧/清帧）
- SC2 动画模板快速创建（Stand/Walk/Attack/Death 等）
- 骨骼选择集管理（保存/加载常用骨骼组）
- 动画拷贝与镜像
- Ghost（洋葱皮）帧预览
- 时间线快捷操作
"""

from . import anim_tools
from . import bone_sets
from . import anim_templates
from . import look_at
from . import anim_fix
from . import sc2_scene_tools
from . import panels

modules = (
    anim_tools,
    bone_sets,
    anim_templates,
    look_at,
    anim_fix,
    sc2_scene_tools,
    panels,
)


def register_props():
    for mod in modules:
        if hasattr(mod, 'register_props'):
            mod.register_props()


def get_classes():
    cls_list = []
    for mod in modules:
        if hasattr(mod, 'classes'):
            cls_list.extend(mod.classes)
    return cls_list


classes = tuple(get_classes())
