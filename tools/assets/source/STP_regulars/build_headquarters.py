"""Build field officers on the native headquarters rig and UV layout."""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from build_regulars import material, pdx, bake_surface_maps
from infantry_polish import uniform_material, bake_diffuse, cloth_bag

CONFIG=json.loads((ROOT/'headquarters.json').read_text())
GAME=Path('Z:/SteamLibrary/steamapps/common/Hearts of Iron IV')
DONOR=GAME/'gfx/models/units/army_headquarters/generic_army_headquarters.mesh'


def build(label):
    config=CONFIG[label]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pdx.import_meshfile(str(DONOR),join_materials=False)
    body=next(obj for obj in bpy.data.objects if obj.type=='MESH' and
              not any(mat.get(pdx.PDX_SHADER)=='Collision' for mat in obj.data.materials))
    rig=next(mod.object for mod in body.modifiers if mod.type=='ARMATURE')
    for obj in list(bpy.data.objects):
        if obj not in (body,rig):bpy.data.objects.remove(obj,do_unlink=True)
    body.name=label+'_body';rig.name=label+'_rig'
    # Headwear is a disconnected surface; identify it independently of UV seams.
    keys=[tuple(round(c,4) for c in v.co) for v in body.data.vertices]
    links={key:set() for key in keys}
    for face in body.data.polygons:
        for a,b in zip(face.vertices,(*face.vertices[1:],face.vertices[0])):
            links[keys[a]].add(keys[b]);links[keys[b]].add(keys[a])
    unseen=set(keys);cap=set()
    while unseen:
        first=unseen.pop();component={first};stack=[first]
        while stack:
            for key in links[stack.pop()]:
                if key in unseen:unseen.remove(key);component.add(key);stack.append(key)
        if min(p[2] for p in component)>6.8:
            cap.update(i for i,key in enumerate(keys) if key in component)
    assert cap,label
    uniform_material(body,config['uniform'],label,camouflage=label=='VAL_hq')
    if config['headwear']=='peaked':
        for face in body.data.polygons:
            if all(i in cap for i in face.vertices):face.material_index=1
    else:
        bm=bmesh.new();bm.from_mesh(body.data);bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm,geom=[bm.verts[i] for i in cap],context='VERTS')
        bm.to_mesh(body.data);bm.free()
    if label=='VAL_hq':
        # Fine garment triangles keep interpolated strap weights on the bending torso surface.
        bm=bmesh.new();bm.from_mesh(body.data)
        edges=[edge for edge in bm.edges if edge.calc_length()>.16 and
               all(4.35<v.co.z<6.55 and abs(v.co.x)<1.05 for v in edge.verts)]
        bmesh.ops.subdivide_edges(bm,edges=edges,cuts=3,use_grid_fill=True)
        bmesh.ops.triangulate(bm,faces=list(bm.faces))
        bm.to_mesh(body.data);bm.free()
    bake_diffuse(body,ROOT/f'{label}_body_source.png',label+'_body_diffuse')
    surface=BVHTree.FromPolygons([v.co for v in body.data.vertices],
                                [p.vertices for p in body.data.polygons])
    canvas=material('Officer canvas',config['canvas'])
    trim=material('Officer identification',config['trim'])
    dark=material('Woven dark binding',(.033,.036,.041))
    shell=material('Protective shell',tuple(c*.65 for c in config['canvas']),.65)
    fitting=material('Matte metal fittings',(.11,.12,.12),.48)
    gear=[]

    def mesh(name,vertices,faces,mat,bone='back_mid'):
        data=bpy.data.meshes.new(name);data.from_pydata(vertices,[],faces);data.update()
        obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj)
        obj.data.materials.append(mat)
        obj.vertex_groups.new(name=bone).add(list(range(len(vertices))),1,'REPLACE')
        obj.modifiers.new('Headquarters rig','ARMATURE').object=rig
        gear.append(obj)
        return obj

    def box(name,location,size,mat,bone='back_mid',bevel=.02):
        bpy.ops.mesh.primitive_cube_add(size=1,location=location)
        obj=bpy.context.object;obj.scale=size
        bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
        mod=obj.modifiers.new('Rounded stitched edge','BEVEL');mod.width=bevel;mod.segments=3
        bpy.ops.object.modifier_apply(modifier=mod.name)
        vertices=[tuple(v.co) for v in obj.data.vertices];faces=[tuple(p.vertices) for p in obj.data.polygons]
        bpy.data.objects.remove(obj,do_unlink=True)
        return mesh(name,vertices,faces,mat,bone)

    def front(x,z):
        hit=surface.ray_cast(Vector((x,-3,z)),Vector((0,1,0)))[0]
        assert hit is not None,(label,x,z)
        return hit.y

    def cord(name,points,radius,mat,bone='back_mid'):
        curve=bpy.data.curves.new(name,'CURVE');curve.dimensions='3D';curve.bevel_depth=radius;curve.bevel_resolution=2
        line=curve.splines.new('POLY');line.points.add(len(points)-1)
        for p,co in zip(line.points,points):p.co=(*co,1)
        obj=bpy.data.objects.new(name,curve);bpy.context.scene.collection.objects.link(obj)
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        bpy.ops.object.convert(target='MESH')
        vertices=[tuple(v.co) for v in obj.data.vertices];faces=[tuple(p.vertices) for p in obj.data.polygons]
        bpy.data.objects.remove(obj,do_unlink=True)
        return mesh(name,vertices,faces,mat,bone)

    def rings(name,rows,mat,bone='head',segments=40,closed=False):
        vertices=[]
        for rx,ry,z,cx,cy,tilt in rows:
            for i in range(segments):
                angle=math.tau*i/segments
                vertices.append((cx+rx*math.cos(angle),cy+ry*math.sin(angle),z+tilt*math.cos(angle)))
        faces=[(r*segments+i,r*segments+(i+1)%segments,(r+1)*segments+(i+1)%segments,(r+1)*segments+i)
               for r in range(len(rows)-1) for i in range(segments)]
        if closed:
            faces.extend((tuple(reversed(range(segments))),tuple(range((len(rows)-1)*segments,len(rows)*segments))))
        obj=mesh(name,vertices,faces,mat,bone)
        for face in obj.data.polygons:face.use_smooth=True
        return obj

    def fitted_webbing(name,points,width,axis):
        vertices=[]
        for index,(a,b) in enumerate(zip(points,points[1:])):
            for step in range(5 if index==len(points)-2 else 4):
                center=Vector(a).lerp(Vector(b),step/4)
                for side in (-1,1):
                    guess=center+Vector(axis)*width*.5*side
                    point,normal,_,_=surface.find_nearest(guess)
                    vertices.append(tuple(point+normal*.018))
        obj=mesh(name,vertices,[(2*r,2*r+1,2*r+3,2*r+2) for r in range(len(vertices)//2-1)],canvas)
        for face in obj.data.polygons:face.use_smooth=True
        solid=obj.modifiers.new('Woven webbing thickness','SOLIDIFY');solid.thickness=.018
        bpy.context.view_layer.objects.active=obj;bpy.ops.object.modifier_apply(modifier=solid.name)
        # The upper back bends across several bones; rigid chest weights lift a strap off the coat.
        obj.vertex_groups.clear()
        for vertex in obj.data.vertices:
            hit,_,index,_=surface.find_nearest(vertex.co)
            face=body.data.polygons[index]
            factors=poly_3d_calc([body.data.vertices[i].co for i in face.vertices],hit)
            weights={}
            for i,factor in zip(face.vertices,factors):
                for group in body.data.vertices[i].groups:
                    bone=body.vertex_groups[group.group].name
                    weights[bone]=weights.get(bone,0)+max(0,factor)*group.weight
            strongest=sorted(weights.items(),key=lambda pair:pair[1],reverse=True)[:4]
            total=sum(weight for _,weight in strongest)
            assert total>.01,(label,name,tuple(vertex.co))
            for bone,weight in strongest:
                group=obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
                group.add([vertex.index],weight/total,'REPLACE')
        return obj

    if config['headwear']=='beret':
        beret_cloth=material('Blue wool beret',(.060,.085,.12))
        rings('Soft asymmetrical beret',[(.365,.41,7.02,0,0,0),(.39,.42,7.08,0,0,-.025),
              (.47,.43,7.19,.065,-.005,-.09),(.39,.35,7.32,.035,0,-.055),
              (.19,.20,7.37,0,0,-.018),(.03,.035,7.38,0,0,0)],beret_cloth,closed=True)
        rings('Beret cloth band',[(.388,.419,7.02,0,0,0),(.398,.425,7.09,0,0,0)],dark)
    elif config['headwear']=='helmet':
        rings('Contoured officer helmet',[(.45,.53,6.98,0,-.01,0),(.49,.54,7.15,0,0,0),
              (.44,.49,7.34,0,.025,0),(.31,.36,7.51,0,.025,0),(.04,.06,7.58,0,.025,0)],shell,closed=True)
        rings('Bound helmet rim',[(.455,.535,6.985,0,-.01,0),(.466,.540,7.025,0,-.01,0)],dark)
        for side in (-1,1):
            box('Headset ear cup',(side*.405,.03,6.74),(.12,.22,.29),dark,'head',.05)
        cord('Headset microphone',[(-.46,-.02,6.70),(-.47,-.28,6.54),(-.20,-.52,6.51)],.016,dark,'head')
    elif config['headwear']=='field_hat':
        rings('Northern field hat brim',[(.39,.43,7.03,0,0,0),(.63,.64,7.035,0,-.05,.055),
              (.63,.64,7.065,0,-.05,.055),(.39,.43,7.09,0,0,0)],dark,closed=True)
        rings('Northern soft crown',[(.40,.43,7.06,0,0,0),(.40,.42,7.30,0,.03,0),
              (.33,.36,7.49,0,.04,0),(.08,.15,7.51,0,.04,0)],shell,closed=True)
        rings('Northern cloth hatband',[(.414,.443,7.105,0,.006,0),(.414,.440,7.20,0,.018,0)],canvas)

    # Small rank tabs follow the chest, leaving the pistol and binoculars envelope clear.
    for side in (-1,1):
        x=side*.22;z=5.92
        box('Collar rank tab',(x,front(x,z)-.024,z),(.12,.027,.12),trim,bevel=.006)
    for i in range(3 if label=='STP_hq' else 2):
        x=.25+i*.075;z=5.55
        box('Woven rank mark',(x,front(x,z)-.027,z),(.045,.024,.022),trim,bevel=.004)

    if label in ('STP_hq','STS_hq','NOD_hq','generic_hq'):
        size=(.35,.20,.51) if label!='STP_hq' else (.40,.22,.56)
        location=Vector((-.69,-.36,4.20))
        for part,kind,vertices,faces in cloth_bag(*size):
            points=[tuple(location+Vector((-x,-y,z))) for x,y,z in vertices]
            mesh('Officer map satchel '+part,points,faces,canvas if kind=='canvas' else dark,'Hip')
    if label in ('STS_hq','NOD_hq','VAL_hq'):
        x=-.56;z=5.39;y=front(x,z)-.11
        box('Compact command radio',(x,y,z),(.18,.18,.29),dark)
        cord('Short command aerial',[(x,y,z+.15),(x+.025,y+.025,z+.47)],.010,dark)
    if label=='VAL_hq':
        for side in (-1,1):
            fitted_webbing('Carrier shoulder webbing',[(side*x,y,z) for x,y,z in
                ((.47,-.49,5.67),(.46,-.37,6.02),(.50,-.15,6.27),(.50,.12,6.29),
                 (.48,.37,6.10),(.48,.53,5.82),(.48,.65,5.18),(.48,.65,4.72))],.105,(1,0,0))
        fitted_webbing('Carrier side and rear belt',[(.79*math.cos(a),.70*math.sin(a),4.72)
            for a in [math.tau*i/32 for i in range(33)]],.12,(0,0,1))
        vertices=[];cols=15;rows=13
        for row in range(rows):
            z=4.56+row/(rows-1)*1.24
            half=.59-.20*max(0,(z-5.45)/.35)
            for col in range(cols):
                x=(col/(cols-1)*2-1)*half
                vertices.append((x,front(x,z)-.07,z))
        obj=mesh('Flexible command carrier',vertices,[(cols*r+i,cols*r+i+1,cols*(r+1)+i+1,cols*(r+1)+i)
                  for r in range(rows-1) for i in range(cols-1)],canvas)
        solid=obj.modifiers.new('Carrier backing','SOLIDIFY');solid.thickness=.035
        bpy.context.view_layer.objects.active=obj;bpy.ops.object.modifier_apply(modifier=solid.name)
        for x in (-.30,.30):
            location=Vector((x,front(x,5.18)-.15,5.18))
            for part,kind,points,faces in cloth_bag(.43,.18,.52):
                mesh('Command pouch '+part,[tuple(location+Vector((-px,-py,pz))) for px,py,pz in points],
                     faces,canvas if kind=='canvas' else dark)
        box('Secure field terminal',(.60,-.33,4.24),(.22,.25,.38),dark,'Hip',.055)
    elif label=='NOD_hq':
        vertices=[];segments=48;cross=10
        for i in range(segments):
            a=math.tau*i/segments
            for j in range(cross):
                t=math.tau*j/cross
                vertices.append(((.30+.035*math.cos(t))*math.cos(a),
                                 .015+(.33+.035*math.cos(t))*math.sin(a),
                                 6.09+.040*math.sin(t)+.010*math.sin(a*3)))
        obj=mesh('Rolled cloth neck warmer',vertices,[(i*cross+j,((i+1)%segments)*cross+j,
            ((i+1)%segments)*cross+(j+1)%cross,i*cross+(j+1)%cross)
            for i in range(segments) for j in range(cross)],dark)
        for face in obj.data.polygons:face.use_smooth=True
    elif label=='STS_hq':
        box('Ochre command patch',(.41,front(.41,5.78)-.024,5.78),(.22,.022,.09),trim,bevel=.007)

    bpy.ops.object.select_all(action='DESELECT')
    for obj in gear:obj.select_set(True)
    bpy.context.view_layer.objects.active=gear[0];bpy.ops.object.join()
    equipment=bpy.context.object;equipment.name=label+'_gear'
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(island_margin=.02);bpy.ops.object.mode_set(mode='OBJECT')
    bake_diffuse(equipment,ROOT/f'{label}_gear_diffuse.png',label+'_gear_diffuse')
    bake_surface_maps(equipment,label)
    scene=bpy.context.scene;scene.cycles.samples=20
    scene.render.resolution_x=850;scene.render.resolution_y=1050;scene.render.resolution_percentage=100
    scene.world=bpy.data.worlds.new('Field officer studio');scene.world.color=(.15,.15,.15)
    bpy.ops.object.camera_add(location=(8,-18,7.5));scene.camera=bpy.context.object
    scene.camera.data.type='ORTHO';scene.camera.data.ortho_scale=8.7
    target=Vector((0,-.06,3.67))
    scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    for position,power in [((4,-8,11),1100),((-5,-2,7),650),((2,5,9),1000)]:
        bpy.ops.object.light_add(type='AREA',location=position);obj=bpy.context.object
        obj.data.energy=power;obj.data.shape='DISK';obj.data.size=6
        obj.rotation_euler=(target-obj.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/f'{label}.blend'))
    for view,position in [('front',(8,-18,7.5)),('back',(-8,18,7.5))]:
        scene.camera.location=position
        scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(ROOT/f'{label}_{view}.png');bpy.ops.render.render(write_still=True)
    report={'donor':str(DONOR),'bones':len(rig.data.bones),
            'body_triangles':sum(len(p.vertices)-2 for p in body.data.polygons),
            'gear_triangles':sum(len(p.vertices)-2 for p in equipment.data.polygons)}
    (ROOT/f'{label}_build.json').write_text(json.dumps(report,indent=2)+'\n')
    print(label,report)


if __name__=='__main__':
    for label in sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else CONFIG:
        build(label)
