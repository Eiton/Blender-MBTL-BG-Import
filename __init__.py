bl_info = {
   "name": "MBTL fbx.json Format",
   "author": "Eiton",
   "version": (1, 0, 0),
   "blender": (4, 0, 0),
   "location": "File > Import",
   "description": "Import files Melty Blood Type Lumina BG file",
   "category": "Import"}

import bpy
import os
import json
import mathutils
import math
from bpy.props import BoolProperty, FloatProperty, StringProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper

class ImportJSON(bpy.types.Operator, ImportHelper):
   bl_idname = "import_scene_fbx.json"
   bl_label = 'Import MBTL (*.json)'
   bl_options = {'UNDO'}
   filename_ext = ".json"
   
   filter_glob: StringProperty(default="*.json", options={'HIDDEN'}, maxlen=255)
   
   def draw(self, context):
      layout = self.layout

   def execute(self, context):
      path = os.path.normpath(self.filepath)
      with open(path, 'rb') as f:
        data = json.load(f)
        parentMap = {}
        materials = []
        for i in range(data["fbxex"]["material"]["count"]):
            material = data["fbxex"]["material"][str(i)]
            mat = bpy.data.materials.new("mat_"+str(i))  
            mat.use_nodes = True            
            mat.use_backface_culling = False
            mat.show_transparent_back = False
            nodes = mat.node_tree.nodes
            nodes.clear()
            tex = nodes.new('ShaderNodeTexImage')
            imagePath = path[:path.rfind("\\")+1]+material["filename"]
            if imagePath[len(imagePath)-3:] == "psd":
                imagePath = imagePath[:len(imagePath)-3]+"dds" 
            tex.image = bpy.data.images.load(imagePath, check_existing=True)
            tex.image.colorspace_settings.is_data = False
            if image_has_alpha(tex.image):
                mat.blend_method = "BLEND"
            pbsdf = nodes.new('ShaderNodeBsdfPrincipled')
            
            attr = nodes.new('ShaderNodeAttribute')
            attr.attribute_type = 'OBJECT'
            attr.attribute_name = 'dst'
            tbsdf = nodes.new('ShaderNodeBsdfTransparent')
            
            addShader = nodes.new('ShaderNodeAddShader')
            
            output = nodes.new('ShaderNodeOutputMaterial')
            output.target = "ALL"
            
            links = mat.node_tree.links
            link = links.new(tex.outputs[0], pbsdf.inputs[0])
            link = links.new(tex.outputs[1], pbsdf.inputs[4])
            link = links.new(pbsdf.outputs[0], addShader.inputs[0])
            link = links.new(attr.outputs[0], tbsdf.inputs[0])
            link = links.new(tbsdf.outputs[0], addShader.inputs[1])
            
            link = links.new(addShader.outputs[0], output.inputs[0])
            materials.append(mat)
        total_frames = 0
        for i in range(data["fbxex"]["anime"]["count"]):
            total_frames = max(total_frames,data["fbxex"]["anime"][str(i)][0])
        bpy.context.scene.render.fps = 60
        bpy.context.scene.frame_start = 0
        bpy.context.scene.frame_end = total_frames
        bpy.context.scene.frame_current = 0
        root = bpy.data.objects.new( "root", None)
        bpy.context.collection.objects.link(root)
        root.rotation_euler = mathutils.Euler((1.5707963705062866, 0.0, 0), 'XYZ')
        root.scale = (1,1,1)
      
        for i in range(data["fbxex"]["node"]["count"]):
            n = data["fbxex"]["node"][str(i)]
            parentMap[str(n["child"])] = format(i,'04d')
            mat = mathutils.Matrix()
            if "matrix" in n:
                m = n["matrix"]
                mat = mathutils.Matrix(((m[0],m[1],m[2],m[3]),(m[4],m[5],m[6],m[7]),(m[8],m[9],m[10],m[11]),(m[12],m[13],m[14],m[15])))
                mat.transpose()
            if str(i) in parentMap and n["sibling"] != -1:
                parentMap[str(n["sibling"])] = parentMap[str(i)]
            if n["type"] == 0:
                new_object = bpy.data.objects.new(format(i,'04d'), None)
                applyTransform(mat,new_object)
                bpy.context.collection.objects.link(new_object)
                if str(i) in parentMap:
                    new_object.parent = bpy.context.collection.objects[parentMap[str(i)]]
                else:
                    new_object.parent = root
            if n["type"] == 1:
                vs = n["vertex"]
                vertices = []
                #no need
                #normals = []
                uvs = []
                for j in range(vs["count"]):
                    v = vs[str(j)]
                    vertices.append((v[0],v[1],v[2]))
                    #no need as blender generates the normal automatically
                    #normals.append((v[3],v[4],v[5]))
                    uvs.append((v[10],v[11]))
                indices = []
                for j in range(int(n["material"]["0"]["vertexindexcount"]//3)):
                    indices.append((n["material"]["0"]["vertexindex"][j*3],n["material"]["0"]["vertexindex"][j*3+1],n["material"]["0"]["vertexindex"][j*3+2]))
                mesh = bpy.data.meshes.new(format(i,'04d'))
                mesh.from_pydata(vertices, [], indices)
                mesh.update()
                new_object = bpy.data.objects.new(format(i,'04d'), mesh)
                applyTransform(mat,new_object)
                new_object.data = mesh                    
                bpy.context.collection.objects.link(new_object)
                if str(i) in parentMap:
                    new_object.parent = bpy.context.collection.objects[parentMap[str(i)]]
                else:
                    new_object.parent = root
                mesh.vertex_colors.new(name="vert_colors")
                color_layer = mesh.vertex_colors["vert_colors"]
                indices_f = list(sum(indices, ()))
                for j in range(len(color_layer.data)):
                    v = vs[str(indices_f[j])]
                    color_layer.data[j].color = [v[6],v[7],v[8],v[9]]
                mesh.uv_layers.new(name="uv")
                uv_layer = mesh.uv_layers["uv"]
                for j in range(len(uv_layer.data)):
                    v = vs[str(indices_f[j])]
                    uv_layer.data[j].uv = [v[10],v[11]]
                new_object.data.materials.append(materials[n["material"]["0"]["index"]])
                if n["blendmode"] == 1:
                    new_object["trans"] = "ADD"
                    new_object["dst"] = 1
            if data["fbxex"]["anime"][str(i)][0] > 0:
                new_object.animation_data_create()
                new_object.animation_data.action = bpy.data.actions.new(name="anim")
                fcurves = new_object.animation_data.action.fcurves
                fcurves.new(data_path="location",index=0)
                fcurves.new(data_path="location",index=1)
                fcurves.new(data_path="location",index=2)
                fcurves.new(data_path="rotation_euler",index=0)
                fcurves.new(data_path="rotation_euler",index=1)
                fcurves.new(data_path="rotation_euler",index=2)
                fcurves.new(data_path="scale",index=0)
                fcurves.new(data_path="scale",index=1)
                fcurves.new(data_path="scale",index=2)
                for j in range(data["fbxex"]["anime"][str(i)][0]):
                    m = data["fbxex"]["anime"][str(i)][(1+j*16):(1+(j+1)*16)]
                    mat = mathutils.Matrix(((m[0],m[1],m[2],m[3]),(m[4],m[5],m[6],m[7]),(m[8],m[9],m[10],m[11]),(m[12],m[13],m[14],m[15])))
                    mat.transpose()
                    (x,y,z) = mat.to_translation()
                    k = fcurves[0].keyframe_points.insert(frame=j,value=x)
                    k.interpolation = "CONSTANT"
                    k = fcurves[1].keyframe_points.insert(frame=j,value=y)
                    k.interpolation = "CONSTANT"
                    k = fcurves[2].keyframe_points.insert(frame=j,value=z)
                    k.interpolation = "CONSTANT"
                    (x,y,z) = mat.to_euler()
                    k = fcurves[3].keyframe_points.insert(frame=j,value=x)
                    k.interpolation = "CONSTANT"
                    k = fcurves[4].keyframe_points.insert(frame=j,value=y)
                    k.interpolation = "CONSTANT"
                    k = fcurves[5].keyframe_points.insert(frame=j,value=z)
                    k.interpolation = "CONSTANT"
                    (x,y,z) = mat.to_scale()
                    k = fcurves[6].keyframe_points.insert(frame=j,value=x)
                    k.interpolation = "CONSTANT"
                    k = fcurves[7].keyframe_points.insert(frame=j,value=y)
                    k.interpolation = "CONSTANT"
                    k = fcurves[8].keyframe_points.insert(frame=j,value=z)
                    k.interpolation = "CONSTANT"
      return {'FINISHED'}
def applyTransform(mat,obj):
    obj.location = mat.to_translation()
    obj.rotation_euler = mat.to_euler()
    obj.scale = mat.to_scale()
def image_has_alpha(img):
    b = 32 if img.is_float else 8
    return (
        img.depth == 2*b or   # Grayscale+Alpha
        img.depth == 4*b      # RGB+Alpha
    )
def menu_func_import(self, context):
   self.layout.operator(ImportJSON.bl_idname, text="MBTL (.json)")

def register():
   from bpy.utils import register_class
   register_class(ImportJSON)
   bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
   from bpy.utils import unregister_class
   unregister_class(ImportJSON)
   bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
   register()
