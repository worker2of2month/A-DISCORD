"""Shared garment materials, equipment shapes and export finishing for infantry and HQs."""
import bmesh
import bpy
import math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc


def uniform_material(obj, tint, label, *, headwear=False, camouflage=False):
    """Retain the donor's seams and skin while tinting the clothed surface."""
    source=obj.data.materials[0]
    material=source.copy()
    material.name=label+' field uniform'
    nodes,links=material.node_tree.nodes,material.node_tree.links
    shader=nodes.get('Principled BSDF')
    original=shader.inputs['Base Color'].links[0].from_socket
    multiply=nodes.new('ShaderNodeMixRGB')
    multiply.blend_type='MULTIPLY';multiply.inputs[0].default_value=1
    multiply.inputs[2].default_value=(*tint,1)
    links.new(original,multiply.inputs[1])
    if camouflage:
        noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=7
        coords=nodes.new('ShaderNodeTexCoord');links.new(coords.outputs['Generated'],noise.inputs['Vector'])
        ramp=nodes.new('ShaderNodeValToRGB');ramp.color_ramp.interpolation='CONSTANT'
        ramp.color_ramp.elements[0].position=.38;ramp.color_ramp.elements[0].color=(*[c*.68 for c in tint],1)
        ramp.color_ramp.elements[1].position=.61;ramp.color_ramp.elements[1].color=(*[c*1.15 for c in tint],1)
        ramp.color_ramp.elements.new(.49).color=(*tint,1)
        links.new(noise.outputs['Fac'],ramp.inputs[0]);links.new(ramp.outputs[0],multiply.inputs[2])
    links.new(multiply.outputs[0],shader.inputs['Base Color'])
    obj.data.materials.append(material)
    # UV seams duplicate vertices; connected garment surfaces still share positions.
    keys=[tuple(round(c,4) for c in vertex.co) for vertex in obj.data.vertices]
    adjacency={key:set() for key in keys}
    for face in obj.data.polygons:
        for a,b in zip(face.vertices,(*face.vertices[1:],face.vertices[0])):
            adjacency[keys[a]].add(keys[b]);adjacency[keys[b]].add(keys[a])
    unseen=set(keys);garment=set()
    while unseen:
        first=unseen.pop();component={first};stack=[first]
        while stack:
            for key in adjacency[stack.pop()]:
                if key in unseen:unseen.remove(key);component.add(key);stack.append(key)
        if min(p[2] for p in component)<4.5 and max(p[2] for p in component)>6.0:
            garment.update(component)
    for face in obj.data.polygons:
        center=face.center
        # Head and hands retain the donor's original skin. Boots retain their leather.
        clothed=(1.6<center.z<6.08 or (6.08<=center.z<6.52 and abs(center.x)>.37))
        if (clothed and abs(center.x)<2.32) or all(keys[i] in garment for i in face.vertices) or (headwear and center.z>6.9):
            face.material_index=len(obj.data.materials)-1
    return material


def bake_diffuse(obj, path, name, size=1024):
    """Bake model materials without direct light, preserving the current UV layout."""
    scene=bpy.context.scene
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    scene.render.engine='CYCLES';scene.cycles.samples=8
    scene.render.bake.use_pass_direct=False;scene.render.bake.use_pass_indirect=False
    scene.render.bake.use_pass_color=True;scene.render.bake.margin=12
    image=bpy.data.images.new(name,size,size,alpha=False)
    for material in obj.data.materials:
        node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=image
        material.node_tree.nodes.active=node
    bpy.ops.object.bake(type='DIFFUSE')
    image.filepath_raw=str(path);image.file_format='PNG';image.save()
    return image


def cloth_bag(width,depth,height,strap_positions=()):
    """Return a filled cloth container with its outward face along local +Y."""
    rows,segments=7,24
    def front(x,t):
        value=depth*.5*(.89+.11*math.sin(math.pi*t)**.6)
        value*=1-.055*(2*x/width)**2
        value-=sum(.022*math.exp(-((x-s)/.055)**2)*math.sin(math.pi*t) for s in strap_positions)
        return value
    vertices=[]
    for row in range(rows):
        t=row/(rows-1)
        taper=.86+.14*math.sin(math.pi*t)**.6
        for i in range(segments):
            a=math.tau*i/segments
            x=math.copysign(abs(math.cos(a))**.43,math.cos(a))*width*.5*taper
            y=math.copysign(abs(math.sin(a))**.43,math.sin(a))*depth*.5
            if y>0:y*=front(x,t)/(depth*.5)
            vertices.append((x,y,(t-.5)*height))
    faces=[(segments*r+i,segments*r+(i+1)%segments,segments*(r+1)+(i+1)%segments,segments*(r+1)+i)
           for r in range(rows-1) for i in range(segments)]
    faces.extend((tuple(reversed(range(segments))),tuple(range(segments*(rows-1),segments*rows))))
    parts=[('Filled shell','canvas',vertices,faces)]
    flap=[]
    for row in range(8):
        t=row/7
        for col in range(11):
            x=(col/10*2-1)*width*(.415-.018*t)
            z=height*(.50-.32*max(0,(t-.3)/.7))
            y=-depth*.25+depth*.76*math.sin(t*math.pi/2)
            y=max(y,front(x,z/height+.5)+.008) if t>.3 else y
            lift=.018*min(1,max(0,(.5-t)/.2))
            flap.append((x,y,z+lift-.008*(1-(2*x/width)**2)))
    parts.append(('Overlapping cloth flap','canvas',flap,
                  [(11*r+i,11*r+i+1,11*(r+1)+i+1,11*(r+1)+i) for r in range(7) for i in range(10)]))
    for x in (-width*.405,width*.405):
        seam=[]
        for row in range(9):
            t=.07+.77*row/8
            for offset in (-.003,.003):
                seam.append((x+offset,front(x,t)+.008,(t-.5)*height))
        parts.append(('Bound side seam','webbing',seam,[(2*r+2,2*r+3,2*r+1,2*r) for r in range(8)]))
    for x in strap_positions or (0,):
        strap=[]
        for row in range(12):
            t=(.05+.90*row/11) if strap_positions else (.62+.20*row/11)
            for side in (-1,1):
                xx=x+side*(.035 if strap_positions else .024)
                yy=front(xx,t)+(.025 if t>.66 else .011)
                strap.append((xx,yy,(t-.5)*height))
        parts.append(('Woven retention','webbing',strap,[(2*r+2,2*r+3,2*r+1,2*r) for r in range(11)]))
    return parts


def tailored_fabric(obj):
    """Round filled cloth volumes and add tension folds before atlas baking."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if e.calc_length()>.22], cuts=1, use_grid_fill=True)
    bm.to_mesh(obj.data)
    bm.free()
    bounds = [(min(v.co[i] for v in obj.data.vertices), max(v.co[i] for v in obj.data.vertices)) for i in range(3)]
    center = Vector(tuple((a+b)/2 for a,b in bounds))
    half = Vector(tuple(max((b-a)/2, .001) for a,b in bounds))
    for vertex in obj.data.vertices:
        q = Vector(tuple((vertex.co[i]-center[i])/half[i] for i in range(3)))
        belly = max(0, 1-q.x*q.x) * max(0, 1-q.z*q.z)
        vertex.co.y += math.copysign(half.y*.14*belly, q.y)
        vertex.co.x *= 1-.055*q.z-.025*q.z*q.z
        vertex.co.y += half.y*.055*math.sin(q.x*8+q.z*4)*math.exp(-((q.z-.60)/.25)**2)
        vertex.co.z += half.z*.018*math.sin(q.x*3+q.y*2)
    for face in obj.data.polygons:
        face.use_smooth = True
    obj.data.set_sharp_from_angle(angle=math.radians(65))


def curve_carrier(obj):
    """Wrap a plate carrier around the rib cage without altering body weights."""
    bpy.context.view_layer.objects.active = obj
    bevel = obj.modifiers.new('Padded carrier edge', 'BEVEL')
    bevel.width, bevel.segments = .045, 3
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    # The centre of a large cap needs vertices before the chest curvature is applied.
    # Subdividing only its perimeter leaves a flat face cutting through the torso.
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts)>4])
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if e.calc_length()>.25], cuts=2, use_grid_fill=True)
    bm.to_mesh(obj.data)
    bm.free()
    for vertex in obj.data.vertices:
        vertex.co.y += .16*(vertex.co.x/.8)**2
    for face in obj.data.polygons:
        face.use_smooth = True


def fitted_head_cloth(body, mesh, material, name, *, hood=False, loose=False):
    """Sample the donor face so cloth follows chin, cheekbones and nose."""
    vertices = [v.co.copy() for v in body.data.vertices]
    faces = [list(p.vertices) for p in body.data.polygons if all(vertices[i].z > 6.0 for i in p.vertices)]
    surface = BVHTree.FromPolygons(vertices, faces)
    segments, rows = 40, 13
    verts, quads = [], []
    for row in range(rows):
        t = row/(rows-1)
        for index in range(segments):
            a = math.tau*index/segments
            front = max(0, -math.sin(a))
            # Front cloth stops below the eyes; temple panels meet the helmet.
            top = 6.71 + (.26 if hood else 0)*(1-front**5)
            z = 6.10+(top-6.10)*t
            direction = Vector((math.cos(a), math.sin(a), 0))
            origin = Vector((0, -.055, z))
            point, normal, _, _ = surface.ray_cast(origin, direction, 1.1)
            if point is None:
                point = origin+Vector((.29*direction.x, .34*direction.y, 0))
            margin = .025 + .035*front**5 + (.025 if loose else .006)*(1-t)
            fold = (.016 if loose else .005)*math.sin(a*5+t*16)*math.sin(math.pi*t)**2
            point += direction*(margin+fold)
            verts.append(tuple(point))
    for row in range(rows-1):
        for index in range(segments):
            a = row*segments+index
            b = row*segments+(index+1)%segments
            quads.append((a,b,b+segments,a+segments))
    obj = mesh(name, verts, quads, material, 'head')
    if hood:
        neck = obj.vertex_groups.new(name='back_mid')
        for vertex in obj.data.vertices:
            weight = min(1, max(.4, .4+(vertex.co.z-6.10)*2))
            obj.vertex_groups['head'].add([vertex.index],weight,'REPLACE')
            neck.add([vertex.index],1-weight,'REPLACE')
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def fitted_armband(obj, body):
    """Fit the band and interpolate sleeve weights to keep both layers together."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if len(f.verts)>4],context='FACES_ONLY')
    bmesh.ops.subdivide_edges(bm,edges=list(bm.edges),cuts=3,use_grid_fill=True)
    bm.to_mesh(obj.data)
    bm.free()
    surface = BVHTree.FromPolygons([v.co for v in body.data.vertices], [list(p.vertices) for p in body.data.polygons])
    axis = Vector((.79,.05,-.63)).normalized()
    matrix, inverse = obj.matrix_world.copy(), obj.matrix_world.inverted()
    for vertex in obj.data.vertices:
        point = matrix@vertex.co
        origin = obj.location+axis*((point-obj.location).dot(axis))
        direction = (point-origin).normalized()
        hit, _, face_index, _ = surface.ray_cast(origin,direction,.6)
        if hit is None:
            hit, _, face_index, _ = surface.find_nearest(point)
        if hit is not None:
            vertex.co = inverse@(hit+direction*.028)
            face = body.data.polygons[face_index]
            factors = poly_3d_calc([body.data.vertices[i].co for i in face.vertices], hit)
            weights = {}
            for index, factor in zip(face.vertices, factors):
                for group in body.data.vertices[index].groups:
                    name = body.vertex_groups[group.group].name
                    weights[name] = weights.get(name, 0) + max(0, factor)*group.weight
            strongest = sorted(weights.items(), key=lambda item: item[1], reverse=True)[:4]
            total = sum(weight for _, weight in strongest)
            if total > 0:
                for name, weight in strongest:
                    group = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
                    group.add([vertex.index], weight/total, 'REPLACE')


def curved_guard(obj):
    """Convex knee and shin plates narrow toward their ends."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.subdivide_edges(bm,edges=[e for e in bm.edges if e.calc_length()>.10],cuts=1,use_grid_fill=True)
    bm.to_mesh(obj.data)
    bm.free()
    width = max(abs(v.co.x) for v in obj.data.vertices)
    height = max(abs(v.co.z) for v in obj.data.vertices)
    for vertex in obj.data.vertices:
        x,z = vertex.co.x/width,vertex.co.z/height
        vertex.co.x *= 1-.15*abs(z)**2
        vertex.co.y += .06*x*x+.025*z*z
    for face in obj.data.polygons:
        face.use_smooth = True


def helmet_shell(mesh, material, rim_material, label):
    """A domed shell with raised brow, ear cut-outs and a lower nape."""
    segments, rows = 40, 11
    wide = 1.03 if label == 'VAL_regular' else 1.0
    verts, faces = [], []
    for row in range(rows):
        t = row/(rows-1)
        radius = math.cos(t*math.pi/2)
        for index in range(segments):
            a = math.tau*index/segments
            front, rear = max(0,-math.sin(a)), max(0,math.sin(a))
            ear = abs(math.cos(a))**8
            lower = 6.83+.16*front**3-.055*rear+.09*ear
            z = lower+(7.35-lower)*math.sin(t*math.pi/2)
            x = wide*.428*radius*math.cos(a)
            y = -.065+wide*.530*radius*math.sin(a)
            verts.append((x,y,z))
    for row in range(rows-1):
        for index in range(segments):
            a = row*segments+index
            b = row*segments+(index+1)%segments
            faces.append((a,b,b+segments,a+segments))
    obj = mesh('Contoured field helmet', verts, faces, material, 'head')
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.00001)
    bm.to_mesh(obj.data)
    bm.free()
    for face in obj.data.polygons:
        face.use_smooth = True
    rim = verts[:segments]
    rim_verts = [(x*scale, -.065+(y+.065)*scale, z+dz) for scale,dz in ((1.004,0),(1.004,.035),(.975,.035),(.975,0)) for x,y,z in rim]
    rim_faces = []
    for row in range(4):
        for index in range(segments):
            a,b = row*segments+index,row*segments+(index+1)%segments
            c,d = ((row+1)%4)*segments+(index+1)%segments,((row+1)%4)*segments+index
            rim_faces.append((a,b,c,d))
    edge = mesh('Bound helmet rim',rim_verts,rim_faces,rim_material,'head')
    for face in edge.data.polygons:
        face.use_smooth = True
    return obj


def polish_normals(obj, minimum_face_area=1e-12):
    """Keep hard corners and area-weight bevel normals without moving the rig."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bmesh.ops.delete(bm, geom=[face for face in bm.faces if face.calc_area() < minimum_face_area], context='FACES_ONLY')
    bmesh.ops.delete(bm, geom=[vertex for vertex in bm.verts if not vertex.link_faces], context='VERTS')
    bm.to_mesh(obj.data)
    bm.free()
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    for face in obj.data.polygons:
        face.use_smooth = True
    obj.data.set_sharp_from_angle(angle=math.radians(58))
    modifier = obj.modifiers.new('Area weighted bevel normals', 'WEIGHTED_NORMAL')
    modifier.keep_sharp = True
    modifier.weight = 50
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def polish_gear(obj, militia=False):
    """Give single-sided straps an inner face and soften the scarf's neck seam."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    unseen = set(bm.faces)
    thin_faces = []
    while unseen:
        first = unseen.pop()
        faces, stack = {first}, [first]
        while stack:
            face = stack.pop()
            for edge in face.edges:
                for adjacent in edge.link_faces:
                    if adjacent in unseen:
                        unseen.remove(adjacent)
                        faces.add(adjacent)
                        stack.append(adjacent)
        vertices = {vertex for face in faces for vertex in face.verts}
        # Open high components are helmet shells, chin/shoulder straps and cloth.
        if min(v.co.z for v in vertices) > 5.35 and any(e.is_boundary for f in faces for e in f.edges):
            thin_faces.extend(faces)
    if thin_faces:
        bmesh.ops.solidify(bm, geom=thin_faces, thickness=.012)
    bm.to_mesh(obj.data)
    bm.free()
    if militia:
        scarf_indices = {index for index, material in enumerate(obj.data.materials)
                         if 'Scarf' in material.name}
        scarf_vertices = {index for face in obj.data.polygons if face.material_index in scarf_indices
                          for index in face.vertices}
        head = obj.vertex_groups.get('head')
        torso = obj.vertex_groups.get('back_mid')
        if head and torso:
            for index in scarf_vertices:
                z = obj.data.vertices[index].co.z
                if z < 6.22 and obj.data.vertices[index].co.y < -.45:
                    obj.data.vertices[index].co.y -= (6.22-z)*.42
                weight = max(0.0, min(1.0, (z - 5.72) / .65))
                head.add([index], weight, 'REPLACE')
                torso.add([index], 1 - weight, 'REPLACE')
    polish_normals(obj)
