"""Build distinct field kits on compatible native infantry bodies.

Run in background Blender; packaging and country assignment remain separate.
"""
import json
import math
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from build_regulars import material, pdx, bake_surface_maps
from infantry_polish import tailored_fabric, curve_carrier, fitted_head_cloth, uniform_material, bake_diffuse, helmet_shell

FACTIONS = json.loads((ROOT / 'factions.json').read_text())


def build(label):
    config = FACTIONS[label]
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'base_inspection' / (config['donor'] + '.blend')))
    scene = bpy.context.scene
    body = max((o for o in scene.objects if o.type == 'MESH' and not o.hide_render),
               key=lambda o: len(o.data.polygons))
    rig = next(m.object for m in body.modifiers if m.type == 'ARMATURE')
    for obj in list(scene.objects):
        if obj.type in ('MESH', 'ARMATURE', 'EMPTY') and obj not in (body, rig):
            bpy.data.objects.remove(obj, do_unlink=True)
    body.name = label + '_body'
    rig.name = label + '_rig'
    shader = body.data.materials[0].node_tree.nodes.get('Principled BSDF')
    if label=='NOD_line':
        for vertex in body.data.vertices:
            if 4.55<vertex.co.z<6.10 and abs(vertex.co.x)<.60 and vertex.co.y>.60:
                vertex.co.y=.60+(vertex.co.y-.60)*.65
        bm=bmesh.new();bm.from_mesh(body.data)
        edges=[edge for edge in bm.edges if edge.calc_length()>.16 and
               all(4.35<v.co.z<6.55 and abs(v.co.x)<1.05 for v in edge.verts)]
        bmesh.ops.subdivide_edges(bm,edges=edges,cuts=3,use_grid_fill=True)
        bmesh.ops.triangulate(bm,faces=list(bm.faces))
        bm.to_mesh(body.data);bm.free()
    if 'uniform' in config:
        uniform=uniform_material(body,config['uniform'],label)
        if label=='NOD_line':
            nodes,links=uniform.node_tree.nodes,uniform.node_tree.links
            multiply=next(n for n in nodes if n.type=='MIX_RGB' and n.blend_type=='MULTIPLY')
            luminance=nodes.new('ShaderNodeRGBToBW')
            links.new(multiply.inputs[1].links[0].from_socket,luminance.inputs[0])
            contrast=nodes.new('ShaderNodeMath');contrast.operation='MULTIPLY_ADD'
            contrast.inputs[1].default_value=.80;contrast.inputs[2].default_value=.03
            links.new(luminance.outputs[0],contrast.inputs[0])
            links.new(contrast.outputs[0],multiply.inputs[1])
            leather=body.data.materials[0].copy()
            leather.name='Northern boot leather'
            shader_leather=leather.node_tree.nodes.get('Principled BSDF')
            darken=leather.node_tree.nodes.new('ShaderNodeMixRGB')
            darken.blend_type='MULTIPLY';darken.inputs[0].default_value=1
            darken.inputs[2].default_value=(.24,.25,.27,1)
            leather.node_tree.links.new(shader_leather.inputs['Base Color'].links[0].from_socket,darken.inputs[1])
            leather.node_tree.links.new(darken.outputs[0],shader_leather.inputs['Base Color'])
            body.data.materials.append(leather)
            # This donor joins hands and boots to the garment across UV seams.
            uniform_index=list(body.data.materials).index(uniform)
            uv=body.data.uv_layers.active.data
            for face in body.data.polygons:
                if abs(face.center.x)>2.0:
                    center_uv=sum((uv[i].uv for i in face.loop_indices),Vector((0,0)))/len(face.loop_indices)
                    hand=center_uv.x>.82 and .57<center_uv.y<.75
                    face.material_index=0 if hand else uniform_index
                elif face.center.z<1.25:face.material_index=len(body.data.materials)-1
        bake_diffuse(body,ROOT/f'{label}_body_source.png',label+'_body_diffuse')
    else:
        shader.inputs['Base Color'].links[0].from_node.image = bpy.data.images.load(
            str(ROOT / f'{label}_body_diffuse.dds'))
    shader.inputs['Roughness'].default_value = .83
    surface = BVHTree.FromPolygons([body.matrix_world @ v.co for v in body.data.vertices],
                                  [list(p.vertices) for p in body.data.polygons])
    canvas = material('Field canvas', config['canvas'])
    plate = material('Protective inserts', config['plate'], .75)
    trim = material('Unit identification', config['trim'])
    webbing = material('Woven straps', (.045, .044, .039))
    metal = material('Phosphated fittings', (.10, .105, .11), .47)
    lens = material('Smoked optics', (.06, .12, .13), .27)
    gear = []
    nodes, connections = canvas.node_tree.nodes, canvas.node_tree.links
    grain = next(n for n in nodes if n.type == 'TEX_NOISE')
    grain.inputs['Scale'].default_value = 42
    grain.inputs['Detail'].default_value = 4
    for element,factor in zip(next(n for n in nodes if n.type == 'VALTORGB').color_ramp.elements,(.58,1.25)):
        element.color=tuple(c*factor for c in config['canvas'])+(1,)

    def finish(obj, name, mat, bone='back_mid'):
        obj.name = name
        obj.data.materials.append(mat)
        obj.vertex_groups.new(name=bone).add(list(range(len(obj.data.vertices))), 1, 'REPLACE')
        obj.modifiers.new('Infantry armature', 'ARMATURE').object = rig
        gear.append(obj)
        return obj

    def mesh(name, vertices, faces, mat, bone='back_mid'):
        data = bpy.data.meshes.new(name)
        data.from_pydata(vertices, [], faces)
        data.update()
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        return finish(obj, name, mat, bone)

    def front(x, z):
        point, _, _, _ = surface.ray_cast(Vector((x, -3, z)), Vector((0, 1, 0)), 6)
        return point.y if point is not None else -.55

    def surface_weights(obj):
        obj.vertex_groups.clear()
        for vertex in obj.data.vertices:
            hit,_,index,_=surface.find_nearest(obj.matrix_world@vertex.co)
            assert hit is not None
            face=body.data.polygons[index]
            factors=poly_3d_calc([body.matrix_world@body.data.vertices[i].co for i in face.vertices],hit)
            weights={}
            for i,factor in zip(face.vertices,factors):
                for group in body.data.vertices[i].groups:
                    name=body.vertex_groups[group.group].name
                    weights[name]=weights.get(name,0)+max(0,factor)*group.weight
            strongest=sorted(weights.items(),key=lambda item:item[1],reverse=True)[:4]
            total=sum(weight for _,weight in strongest)
            assert total>0
            for name,weight in strongest:
                group=obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
                group.add([vertex.index],weight/total,'REPLACE')

    def box(name, location, size, mat, bone='back_mid', bevel=.035):
        bpy.ops.mesh.primitive_cube_add(size=1, location=location)
        obj = bpy.context.object
        obj.scale = size
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        mod = obj.modifiers.new('Soft manufactured edges', 'BEVEL')
        mod.width, mod.segments = bevel, 3
        bpy.ops.object.modifier_apply(modifier=mod.name)
        if mat == canvas and min(size) > .10:
            tailored_fabric(obj)
        return finish(obj, name, mat, bone)

    def chest(name, x, z, size, mat=canvas, extra=.025):
        return box(name, (x, front(x, z)-size[1]/2-extra, z), size, mat)

    def ribbon(name, points, width, mat=webbing, bone='back_mid', *, level_back=False):
        path=[]
        for a,b in zip(points,points[1:]):
            steps=max(2,math.ceil((Vector(b)-Vector(a)).length/.10))
            path.extend(Vector(a).lerp(Vector(b),i/steps) for i in range(steps))
        path.append(Vector(points[-1]))
        vertices=[]
        northern_strap=label=='NOD_line' and name=='Northern shoulder strap'
        support=shoulder_surface if northern_strap else surface
        for index,point in enumerate(path):
            _,normal,_,_=support.find_nearest(point)
            tangent=path[min(index+1,len(path)-1)]-path[max(0,index-1)]
            mountain_strap=label=='SRP_highland' and name=='Mountain pack shoulder'
            across=Vector((1,0,0)) if mountain_strap or northern_strap else Vector((0,0,1)) if level_back else normal.cross(tangent).normalized()
            for side in (-1,1):
                target=point+across*(side*width/2)
                if mountain_strap and target.y<-.2 and target.z<5.9:
                    y=min(front(target.x,target.z+offset) for offset in (-.10,-.05,0,.05,.10))-.040
                    vertices.append((target.x,y,target.z))
                elif level_back:
                    hit,_,_,_=surface.ray_cast(Vector((target.x,3,target.z)),Vector((0,-1,0)),6)
                    vertices.append((target.x,hit.y+.055 if hit is not None else target.y,target.z))
                else:
                    hit,normal,_,_=support.find_nearest(target)
                    vertices.append(tuple(hit+normal*(.018 if northern_strap else .055) if hit is not None else target))
        obj = mesh(name, vertices, [(2*i,2*i+1,2*i+3,2*i+2) for i in range(len(path)-1)], mat, bone)
        mod = obj.modifiers.new('Woven thickness', 'SOLIDIFY')
        mod.thickness = .018
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        if label=='NOD_line' and name=='Northern shoulder strap':surface_weights(obj)
        return obj

    def cord(name,points,radius,mat,bone='back_mid'):
        curve=bpy.data.curves.new(name,'CURVE')
        curve.dimensions='3D'
        curve.resolution_u=2
        curve.bevel_depth=radius
        curve.bevel_resolution=2
        line=curve.splines.new('POLY')
        line.points.add(len(points)-1)
        for point,co in zip(line.points,points): point.co=(*co,1)
        obj=bpy.data.objects.new(name,curve)
        scene.collection.objects.link(obj)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active=obj
        bpy.ops.object.convert(target='MESH')
        return finish(bpy.context.object,name,mat,bone)

    def pouch(x, z, width=.32, height=.51, depth=.26):
        y=front(x,z)-depth/2-.065
        vertices=[]
        rows,segments=9,24
        for row in range(rows):
            t=row/(rows-1)
            taper=.80+.20*math.sin(math.pi*t)**.6
            for i in range(segments):
                a=math.tau*i/segments
                xx=math.copysign(abs(math.cos(a))**.42,math.cos(a))*width*.5*taper
                yy=math.copysign(abs(math.sin(a))**.44,math.sin(a))*depth*.5
                yy*=.65+.35*math.sin(math.pi*t)**.4
                yy+=.013*math.sin(xx/width*11+t*5)*math.exp(-((t-.72)/.17)**2)
                zz=z+(t-.5)*height+.01*math.cos(3*a)*math.sin(math.pi*t)
                vertices.append((x+xx,y+yy,zz))
        faces=[(segments*r+i,segments*r+(i+1)%segments,segments*(r+1)+(i+1)%segments,segments*(r+1)+i) for r in range(rows-1) for i in range(segments)]
        faces.extend((tuple(reversed(range(segments))),tuple(range(segments*(rows-1),segments*rows))))
        obj=mesh('Soft canvas magazine pouch',vertices,faces,canvas)
        for face in obj.data.polygons: face.use_smooth=True
        flap=[]
        for row in range(6):
            t=row/5
            for col in range(13):
                u=col/12*2-1
                flap.append((x+u*width*.49,y-depth*.51-.012-.014*(1-u*u),
                             z+height*(.49-.33*t)-.025*(1-u*u)*t))
        flap_faces=[(13*r+i,13*r+i+1,13*(r+1)+i+1,13*(r+1)+i) for r in range(5) for i in range(12)]
        obj=mesh('Flexible overlapping flap',flap,flap_faces,canvas)
        for face in obj.data.polygons: face.use_smooth=True
        solid=obj.modifiers.new('Canvas flap thickness','SOLIDIFY');solid.thickness=.012
        bpy.context.view_layer.objects.active=obj
        bpy.ops.object.modifier_apply(modifier=solid.name)
        cord('Flap stitched hem',flap[-13:],.0045,webbing)
        for side in (-1,1):
            cord('Pouch side seam',[(x+side*width*.43,y-depth*.40,z+height*(t-.5)) for t in (.08,.25,.5,.72,.89)],.004,webbing)
        box('Cloth fastening tab',(x,y-depth*.57-.012,z+height*.16),(.046,.015,.15),webbing,bevel=.006)
        box('Fastener stud',(x,y-depth*.59-.013,z+height*.18),(.025,.012,.025),metal,bevel=.011)

    def carrier():
        first_part=len(gear)
        vertices=[]
        for row in range(11):
            t=row/10;z=(4.64+1.12*t) if label=='NOD_line' else (4.47+1.35*t)
            width=(.58 if label=='NOD_line' else .62)-.17*max(0,(t-.65)/.35)
            for col in range(13):
                x=(col/12*2-1)*width
                vertices.append((x,front(x,z)-.055,z))
        obj=mesh('Continuous woven carrier',vertices,[(13*r+i,13*r+i+1,13*(r+1)+i+1,13*(r+1)+i) for r in range(10) for i in range(12)],canvas)
        mod=obj.modifiers.new('Padded backing','SOLIDIFY');mod.thickness=.045
        bpy.context.view_layer.objects.active=obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        for face in obj.data.polygons:face.use_smooth=True
        cord('Carrier bound edge',vertices[:13],.014,webbing)
        if label=='NOD_line':
            waist_surface=BVHTree.FromPolygons([v.co for v in body.data.vertices],
                [list(p.vertices) for p in body.data.polygons
                 if all(abs(body.data.vertices[i].co.x)<1.15 and 4.2<body.data.vertices[i].co.z<5.1 for i in p.vertices)])
            belt=[]
            for z in (4.54,4.73):
                for i in range(64):
                    a=math.tau*i/64;direction=Vector((math.cos(a),math.sin(a),0))
                    hit,normal,_,_=waist_surface.ray_cast(direction*3+Vector((0,0,z)),-direction,3)
                    assert hit is not None
                    belt.append((hit.x+normal.x*.025,hit.y+normal.y*.025,z))
            mesh('Continuous field belt',belt,[(i,(i+1)%64,(i+1)%64+64,i+64) for i in range(64)],webbing)
            for obj in gear[first_part:]:surface_weights(obj)
            return
        for side in (-1,1):
            ribbon('Side carrier belt',[(side*.55,-.52,4.71),(side*.78,0,4.71),(side*.55,.55,4.71)],.20)
        ribbon('Rear carrier belt',[(-.55,.65,4.71),(0,.72,4.71),(.55,.65,4.71)],.20,level_back=True)

    def insert(name,cx,z,width,height,offset=.175):
        vertices=[]
        cols,rows=11,9
        for depth in (offset-.045,offset):
            for row in range(rows):
                v=row/(rows-1)-.5
                half=.5-.18*max(0,(v-.23)/.27)
                for col in range(cols):
                    x=cx+(col/(cols-1)*2-1)*half*width
                    zz=z+v*height
                    vertices.append((x,front(x,zz)-depth,zz))
        layer=cols*rows
        faces=[]
        for side in (0,1):
            for row in range(rows-1):
                for col in range(cols-1):
                    a=side*layer+row*cols+col
                    face=(a,a+1,a+cols+1,a+cols)
                    faces.append(face if side else tuple(reversed(face)))
        boundary=list(range(cols))+[r*cols+cols-1 for r in range(1,rows)]+list(range(layer-2,layer-cols-1,-1))+[r*cols for r in range(rows-2,0,-1)]
        for a,b in zip(boundary,boundary[1:]+boundary[:1]):faces.append((a,b,b+layer,a+layer))
        obj=mesh(name,vertices,faces,plate)
        bevel=obj.modifiers.new('Bound protective edge','BEVEL');bevel.width=.025;bevel.segments=3
        bpy.context.view_layer.objects.active=obj
        bpy.ops.object.modifier_apply(modifier=bevel.name)
        for face in obj.data.polygons:face.use_smooth=True
        return obj

    if label in ('WRK_line','VAD_line','NOD_line','SRP_highland'):
        # Separate the disconnected helmet shell from the shared body atlas.
        keys=[tuple(round(float(c),4) for c in v.co) for v in body.data.vertices]
        links={key:set() for key in keys}
        for face in body.data.polygons:
            for a,b in zip(face.vertices,(*face.vertices[1:],face.vertices[0])):
                links[keys[a]].add(keys[b]);links[keys[b]].add(keys[a])
        unseen=set(keys);helmet_ids=set()
        while unseen:
            key=unseen.pop();component={key};pending=[key]
            while pending:
                for other in links[pending.pop()]:
                    if other in unseen:unseen.remove(other);component.add(other);pending.append(other)
            if min(p[2] for p in component)>(6.6 if label=='NOD_line' else 6.7) and max(p[2] for p in component)>7.3:
                helmet_ids.update(i for i,k in enumerate(keys) if k in component)
        assert helmet_ids,label
        ids=sorted(helmet_ids);remap={old:new for new,old in enumerate(ids)}
        faces=[tuple(remap[i] for i in p.vertices) for p in body.data.polygons if all(i in helmet_ids for i in p.vertices)]
        helmet=mesh('Field helmet shell',[tuple(body.data.vertices[i].co) for i in ids],faces,canvas,'head')
        if label == 'WRK_line':
            for vertex in helmet.data.vertices:
                t=min(1,max(0,(vertex.co.z-6.75)/.64))
                bulge=1+.065*math.sin(math.pi*t)
                vertex.co.x*=bulge
                vertex.co.y*=bulge
                if vertex.co.y<-.30 and t<.3:
                    vertex.co.y-=.04*(1-t/.3)
            mod=helmet.modifiers.new('Rounded shell transitions','SUBSURF')
            mod.levels=1
            bpy.context.view_layer.objects.active=helmet
            bpy.ops.object.modifier_apply(modifier=mod.name)
        for face in helmet.data.polygons:face.use_smooth=True
        bm=bmesh.new();bm.from_mesh(body.data);bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm,geom=[bm.verts[i] for i in ids],context='VERTS');bm.to_mesh(body.data);bm.free()
        # Surface weights must use the face indices after the headwear was removed.
        surface=BVHTree.FromPolygons([body.matrix_world@v.co for v in body.data.vertices],
                                    [list(p.vertices) for p in body.data.polygons])

        if label=='NOD_line':
            gear.remove(helmet);bpy.data.objects.remove(helmet,do_unlink=True)
            helmet_shell(mesh,canvas,webbing,label)
            # Shoulder webbing must not snap to the nearby neck or jaw.
            shoulder_surface=BVHTree.FromPolygons([v.co for v in body.data.vertices],
                [list(p.vertices) for p in body.data.polygons
                 if all(4.2<body.data.vertices[i].co.z<6.30 and abs(body.data.vertices[i].co.x)<1.15 for i in p.vertices)])
            head_surface=BVHTree.FromPolygons([v.co for v in body.data.vertices],
                [list(p.vertices) for p in body.data.polygons
                 if all(6.15<body.data.vertices[i].co.z<7.3 and abs(body.data.vertices[i].co.x)<.45 for i in p.vertices)])
            for side in (-1,1):
                guides=[Vector((side*.40,-.05,6.91)),Vector((side*.36,-.31,6.64)),Vector((side*.20,-.40,6.34))]
                path=[a.lerp(b,i/7) for a,b in zip(guides,guides[1:]) for i in range(7)]+guides[-1:]
                vertices=[]
                for point in path:
                    for offset in (-.018,.018):
                        hit,normal,_,_=head_surface.find_nearest(point+Vector((offset,0,0)))
                        assert hit is not None
                        vertices.append(tuple(hit+normal*.014))
                mesh('Helmet retention strap',vertices,[(i*2,i*2+1,i*2+3,i*2+2) for i in range(len(path)-1)],webbing,'head')
        if label=='SRP_highland':
            # A low cloth crown retains the broad mountain-cap brim.
            for vertex in helmet.data.vertices:
                vertex.co.z=6.98+(vertex.co.z-6.98)*.70
                vertex.co.x*=.97
            hat_surface=BVHTree.FromPolygons([v.co for v in helmet.data.vertices],[p.vertices for p in helmet.data.polygons])
            band=[]
            for z in (7.035,7.075):
                for i in range(48):
                    direction=Vector((math.cos(math.tau*i/48),math.sin(math.tau*i/48),0))
                    hit=hat_surface.ray_cast(Vector((0,0,z)),direction)[0]
                    assert hit is not None,('mountain cap band',i,z)
                    band.append(tuple(hit+direction*.007))
            mesh('Fitted mountain cap band',band,[(i,(i+1)%48,(i+1)%48+48,i+48) for i in range(48)],webbing,'head')

    if label == 'WRK_line':
        carrier()
        for side in (-1,1):
            insert('Split curved chest insert',side*.28,5.35,.51,.78)
            pouch(side*.24, 4.78, .36)
            pouch(side*.68, 4.68, .25, .46)
            ribbon('Carrier shoulder', [(side*.42,-.62,5.65),(side*.40,-.20,6.03),(side*.39,.25,6.02),(side*.42,.60,5.55),(side*.4,.65,4.71)], .13)
        chest('Ochre chest tab', .32, 5.60, (.20,.025,.075), trim, .187)
        radio=chest('Compact radio', -.63, 5.50, (.19,.20,.33), webbing)
        box('Short radio antenna',tuple(radio.location+Vector((0,0,.31))),(.018,.018,.30),webbing,bevel=.004)
    elif label == 'TVA_technical':
        for x in (-.42,.42):
            ribbon('Technical harness', [(x,front(x,4.6)-.04,4.6),(x,-.65,5.45),(x,-.25,5.96),(x,.40,5.80),(x,.70,4.65)], .16)
        for z in (4.75,5.26):
            pouch(-.36,z,.28,.42)
        pouch(.38,5.12,.40,.73,.30)
        chest('Field scanner', .48,4.40,(.35,.22,.28),metal)
        chest('Scanner glass', .48,4.41,(.22,.025,.14),lens,.245)
        chest('Technical identity', -.30,5.68,(.18,.025,.085),trim)
        cord('Instrument cable',[(.47,-.70,5.44),(.60,-.68,5.65),(.48,-.64,5.74),(.36,-.63,5.60)],.012,webbing)
        # Recessed lenses share a bridge and a strap around the helmet.
        for x in (-.20,.20):
            points=[(x+.175*math.cos(a),-.555-.035*math.sin(a)**2,7.08+.107*math.sin(a)) for a in [math.tau*i/32 for i in range(33)]]
            cord('Moulded optical frame',points,.025,webbing,'head')
            mesh('Recessed smoked lens',[(x,-.557,7.08)]+[(x+.151*math.cos(math.tau*i/32),-.558,7.08+.084*math.sin(math.tau*i/32)) for i in range(32)],[(0,i+1,(i+1)%32+1) for i in range(32)],lens,'head')
        cord('Flexible optical bridge',[(-.055,-.56,7.08),(0,-.60,7.095),(.055,-.56,7.08)],.021,webbing,'head')
        strap=[(.50*math.cos(a),-.02+.55*math.sin(a),7.07) for a in [math.pi+math.tau*i/48 for i in range(49)]]
        ribbon('Flat optical retaining band',strap,.065,webbing,'head')
    elif label == 'VAD_line':
        carrier()
        for z,width,depth in ((5.50,.98,.245),(5.20,1.08,.205),(4.90,1.15,.165)):
            insert('Overlapping curved torso armour',0,z,width,.38,depth)
        for x in (-.63,.63):
            pouch(x,4.62,.27,.57)
            ribbon('Armour suspender',[(x*.72,-.69,5.60),(x*.65,-.18,6.05),(x*.7,.55,5.66),(x*.7,.65,4.71)],.12)
        chest('Burgundy unit tab',.29,5.52,(.20,.025,.065),trim,.257)
    elif label == 'IVN_line':
        for x in (-.52,0,.52):
            pouch(x,4.65,.36,.45)
        for side in (-1,1):
            ribbon('Cross webbing',[(side*.63,front(side*.63,4.7)-.045,4.7),(side*.2,-.65,5.35),(-side*.39,-.33,5.94)],.085)
        # The upper folds follow the neck; the loose lower edge rests on the chest.
        vertices=[]
        for row in range(11):
            t=row/10
            for i in range(49):
                a=math.tau*i/48+.12
                forward=max(0,-math.sin(a))
                radius=.34+.05*(1-t)+.009*math.sin(t*math.pi*3+1.7*math.sin(a))
                point=Vector((radius*math.cos(a),.015+(radius+.05)*math.sin(a),
                              6.20-(.08+.50*forward**4)*(1-t)+.02*math.sin(a+.7)*(1-t)))
                radial=Vector((point.x,point.y,0)).normalized()
                center=Vector((0,0,point.z))
                hit,_,_,_=surface.ray_cast(center+radial*2,-radial,2)
                if hit is not None and (hit-center).length+.035>(point-center).length:
                    point=center+radial*((hit-center).length+.035)
                vertices.append(tuple(point))
        obj=mesh('Draped field scarf',vertices,[(49*r+i,49*r+i+1,49*(r+1)+i+1,49*(r+1)+i) for r in range(10) for i in range(48)],canvas)
        surface_weights(obj)
        for face in obj.data.polygons:face.use_smooth=True
        hem=cord('Scarf free hem',vertices[:49],.008,canvas)
        surface_weights(hem)
        chest('Teal field tab',.34,5.62,(.16,.025,.07),trim)
    elif label=='NOD_line':
        carrier()
        insert('Northern light chest insert',0,5.38,.74,.61,.105)
        for side in (-1,1):
            pouch(side*.25,4.96,.36,.49,.21)
            ribbon('Northern shoulder strap',[(side*.45,-.62,5.56),(side*.55,-.22,5.95),
                   (side*.60,0,6.14),(side*.60,.23,6.17),(side*.50,.50,5.95),
                   (side*.40,.68,5.25),(side*.40,.65,4.74)],.13)
        chest('Northern identification',.20,5.62,(.15,.020,.052),trim,.12)
        radio=chest('Northern field radio',-.54,5.42,(.16,.16,.31),webbing)
        box('Short field aerial',tuple(radio.location+Vector((0,0,.32))),(.017,.017,.30),webbing,bevel=.004)
        box('Field utility pocket',(.72,.20,4.43),(.23,.32,.40),canvas,'Hip',.06)
    elif label=='SRP_highland':
        for side in (-1,1):
            pouch(side*.37,4.63,.36,.49)
            ribbon('Mountain pack shoulder',[(side*.45,-.56,4.6),(side*.44,-.57,5.45),
                   (side*.39,-.16,6.01),(side*.40,.53,5.62),(side*.40,.70,4.60)],.12,canvas)
        box('Highland hiking pack',(0,.79,5.08),(.82,.40,1.04),canvas,bevel=.12)
        for radius in (.24,.28,.32):
            cord('Coiled climbing rope',[(radius*math.cos(a),1.04,5.16+radius*1.30*math.sin(a))
                 for a in [math.tau*i/48 for i in range(49)]],.023,trim)
        box('Rope retaining webbing',(0,1.076,5.16),(.075,.035,.88),canvas,bevel=.012)
        box('Rope retaining buckle',(0,1.10,5.42),(.11,.04,.12),metal,bevel=.015)
        cord('Tied rope end',[(.13,1.045,4.91),(.21,1.065,4.72),(.33,1.03,4.62),(.39,.99,4.74)],.020,trim)
        chest('Highland yellow field tab',.28,5.54,(.20,.026,.065),trim)
        box('Mountain equipment pouch',(-.73,.02,4.30),(.24,.39,.49),canvas,'Hip',.07)
    else:
        pouch(-.39,4.64,.34,.47)
        pouch(.39,4.64,.34,.47)
        ribbon('Diagonal canvas strap',[(-.75,-.55,4.55),(0,-.68,5.26),(.46,-.26,5.94)],.12,canvas)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in gear:
        obj.select_set(True)
    bpy.context.view_layer.objects.active=gear[0]
    bpy.ops.object.join()
    equipment=bpy.context.object
    equipment.name=label+'_gear'
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(island_margin=.02)
    bpy.ops.object.mode_set(mode='OBJECT')
    image=bpy.data.images.new(label+'_gear_diffuse',1024,1024,alpha=False)
    for mat in equipment.data.materials:
        node=mat.node_tree.nodes.new('ShaderNodeTexImage')
        node.image=image
        mat.node_tree.nodes.active=node
    scene.render.engine='CYCLES'
    scene.cycles.samples=8
    scene.render.bake.use_pass_direct=False
    scene.render.bake.use_pass_indirect=False
    scene.render.bake.use_pass_color=True
    scene.render.bake.margin=12
    bpy.ops.object.bake(type='DIFFUSE')
    image.filepath_raw=str(ROOT/f'{label}_gear_diffuse.png')
    image.file_format='PNG'
    image.save()
    bake_surface_maps(equipment,label)
    scene.cycles.samples=24
    scene.render.resolution_x=850
    scene.render.resolution_y=1050
    scene.view_settings.view_transform='AgX'
    for light in bpy.data.lights:
        light.energy*=.55
    scene.world.color=(.12,.12,.12)
    target=Vector((0,-.06,3.67))
    scene.camera.data.ortho_scale=8.7
    for view,position in (('front',(8,-18,7.5)),('back',(-8,18,7.5))):
        scene.camera.location=position
        scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler()
        if view=='front':
            bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/f'{label}.blend'))
        scene.render.filepath=str(ROOT/f'{label}_{view}.png')
        bpy.ops.render.render(write_still=True)
    report={'donor':config['donor'],'body_triangles':sum(len(p.vertices)-2 for p in body.data.polygons),
            'gear_triangles':sum(len(p.vertices)-2 for p in equipment.data.polygons),'bones':len(rig.data.bones)}
    for obj in (body,equipment):
        assert all(v.groups for v in obj.data.vertices), obj.name
        assert all(g.name in rig.data.bones for g in obj.vertex_groups), obj.name
    (ROOT/f'{label}_build.json').write_text(json.dumps(report,indent=2))
    print(label,report)


if __name__=='__main__':
    labels=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else FACTIONS
    for label in labels:
        build(label)
