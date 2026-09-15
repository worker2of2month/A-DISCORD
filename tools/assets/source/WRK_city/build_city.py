"""Build nine static native HOI4 city meshes with grounded, centered origins."""
import bpy
import bmesh
import json
import hashlib
import math
import sys
from pathlib import Path
from types import SimpleNamespace
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
MOD = ROOT.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent/'STP_regulars'))
from export_verify import pdx, pdx_data, preview_gloss
from package_city import convex_hull

NAMES = ('tower_admin', 'tower_business', 'tower_residential',
         'quarter_business', 'quarter_mixed', 'quarter_residential',
         'stelander_spire', 'stelander_twin', 'stelander_arcology')
MATERIALS = ('glass', 'concrete', 'roof', 'detail', 'glass_teal', 'glass_bronze', 'glass_silver', 'screen')


class Builder:
    def __init__(self, name):
        self.name, self.vertices, self.faces, self.uvs, self.materials = name, [], [], [], []
        self.buildings=0

    def face(self, points, material, uv):
        start = len(self.vertices)
        self.vertices.extend(points)
        self.faces.append(tuple(range(start, start+len(points))))
        self.materials.append(MATERIALS.index(material))
        self.uvs.append(uv)

    def prism(self, x, y, z, width, depth, height, material='glass', chamfer=.07, color=0):
        c = min(chamfer, width*.2, depth*.2)
        outline = [(-width/2+c,-depth/2),(width/2-c,-depth/2),
                   (width/2,-depth/2+c),(width/2,depth/2-c),
                   (width/2-c,depth/2),(-width/2+c,depth/2),
                   (-width/2,depth/2-c),(-width/2,-depth/2+c)]
        low = [(x+a,y+b,z) for a,b in outline]
        high = [(a,b,z+height) for a,b,_ in low]
        palette_uv = [(color/8+.015,.15),((color+1)/8-.015,.15),
                      ((color+1)/8-.015,.85),(color/8+.015,.85)]
        for i in range(8):
            j=(i+1)%8
            length=math.dist(outline[i],outline[j])
            if material=='detail':
                self.face([low[i],low[j],high[j],high[i]],material,palette_uv)
                continue
            # Tile by geometry, not sampler state: JoroDox clamps DDS edges.
            # Every patch stays in 0..1, with the same window density in HOI4.
            for u in range(math.ceil(length/1.45)):
                u0,u1=u*1.45/length,min(1,(u+1)*1.45/length)
                a=Vector(low[i]).lerp(Vector(low[j]),u0)
                b=Vector(low[i]).lerp(Vector(low[j]),u1)
                for v in range(math.ceil(height/2.6)):
                    z0,z1=v*2.6,min(height,(v+1)*2.6)
                    points=[tuple(a+Vector((0,0,z0))),tuple(b+Vector((0,0,z0))),
                            tuple(b+Vector((0,0,z1))),tuple(a+Vector((0,0,z1)))]
                    du,dv=min(1,(u1-u0)*length/1.45),min(1,(z1-z0)/2.6)
                    self.face(points,material,[(0,0),(du,0),(du,dv),(0,dv)])
        cap_uv=[((a+width/2)/max(width,depth),(b+depth/2)/max(width,depth)) for a,b in outline]
        if material=='detail':
            cap_uv=[(color/8+.02+(a/width+.5)*.08,.2+(b/depth+.5)*.6) for a,b in outline]
        self.face(high,'detail' if material=='detail' else 'roof',cap_uv)
        self.face(low[::-1],material,cap_uv[::-1])

    def building(self,x,y,w,d,h,style=0,base=.10,glass=None):
        self.prism(x,y,-.45,w+.10,d+.10,.55,'concrete')
        self.prism(x,y,base,w,d,.34,'concrete')
        glass=glass or (('glass_teal','glass_bronze','glass_silver') if self.name.startswith('stelander') else ('glass','glass_silver','glass'))[self.buildings%3]
        self.buildings+=1
        self.prism(x,y,base+.34,w*.96,d*.96,h-.44,glass)
        self.prism(x,y,base+h-.10,w+.025,d+.025,.10,'concrete')
        # Thin structural belts and recessed roof plant remain legible at map zoom.
        if style==0:
            for z in (.9,1.8,2.7,3.6,4.5,5.4):
                if z<h-.18:
                    self.prism(x,y,base+z,w+.025,d+.025,.055,'concrete')
        elif style==1:
            for dx in (-w*.32,w*.32):
                self.prism(x+dx,y-d*.485,base+.32,.055,.055,h-.4,'detail',.012,2)
                self.prism(x+dx,y+d*.485,base+.32,.055,.055,h-.4,'detail',.012,2)
        else:
            self.prism(x,y,base+h*.56,w+.05,d+.05,.11,'concrete')
        self.prism(x-w*.14,y+d*.13,base+h,w*.36,d*.38,.16,'roof',.04)
        self.prism(x+w*.25,y-d*.19,base+h,.19,.22,.11,'detail',.025,1)

    def screen(self,x,y,z,size,advert=0):
        self.prism(x,y+.025,z-.04,size+.09,.09,size+.08,'detail',.025,1)
        u=(advert%2)*.5
        v=(1-advert//2)*.5
        self.face([(x-size/2,y-.026,z),(x+size/2,y-.026,z),
                   (x+size/2,y-.026,z+size),(x-size/2,y-.026,z+size)],
                  'screen',[(u+.015,v+.015),(u+.485,v+.015),(u+.485,v+.485),(u+.015,v+.485)])

    def plaza(self,w,d):
        self.prism(0,0,-.96,w,d,1.02,'concrete',.18)
        # Walkways break the base into recognizable city blocks without opaque terrain overlays.
        self.prism(0,0,.062,w-.18,.30,.018,'detail',.04,4)

    def garden(self,x,y,w=.55,d=.45):
        self.prism(x,y,.08,w+.12,d+.12,.12,'concrete',.06)
        self.prism(x,y,.20,w,d,.025,'detail',.06,3)
        self.prism(x,y,.22,w*.48,d*.60,.20,'detail',.12,3)

    def object(self, mats):
        mesh=bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.vertices,[],self.faces)
        mesh.update()
        obj=bpy.data.objects.new(self.name,mesh)
        bpy.context.scene.collection.objects.link(obj)
        used=sorted(set(self.materials))
        for index in used:
            mesh.materials.append(mats[index])
        uv=mesh.uv_layers.new(name='UVMap')
        for face,coords,material in zip(mesh.polygons,self.uvs,self.materials):
            face.material_index=used.index(material)
            for loop,point in zip(face.loop_indices,coords):
                uv.data[loop].uv=point
        bm=bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.triangulate(bm,faces=list(bm.faces))
        # Each UV face is disconnected. Keep its authored outward winding;
        # recalculating disconnected islands can reverse individual walls.
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        return obj


def model(name):
    b=Builder(name)
    if name=='tower_admin':
        b.plaza(3.1,2.7)
        b.building(0,0,2.6,2.0,.95,1)
        b.building(0,.15,1.8,1.35,3.95,1,1.05)
        b.building(0,.15,1.25,1.02,1.05,1,5.0)
        b.prism(0,.15,6.08,.63,.68,.25,'detail',.07,2)
        b.prism(-1,-1.10,.12,.15,.4,.48,'detail',.025,2)
        b.prism(1,-1.10,.12,.15,.4,.48,'detail',.025,2)
    elif name=='tower_business':
        b.plaza(3.35,2.65)
        b.building(0,0,2.9,2.2,.6,2)
        b.building(-.76,.10,1.0,1.5,4.9,1,.7)
        b.building(.76,.10,1.0,1.5,3.85,1,.7)
        b.prism(0,.1,3.55,.73,.52,.27,'glass')
        b.prism(0,.1,3.51,.75,.54,.06,'detail',.03,2)
        b.garden(0,-.95,.7,.22)
    elif name=='tower_residential':
        b.plaza(3.15,2.95)
        b.building(-.5,.38,1.6,1.3,4.55,0)
        b.building(.73,-.12,.85,1.75,3.5,0)
        b.building(-.52,-.79,1.65,.65,1.25,0)
        b.garden(-.42,-.66,.7,.45)
        b.prism(-.50,.38,4.80,.65,.65,.25,'concrete')
    elif name.startswith('stelander'):
        b.plaza(3.8,3.5)
        if name=='stelander_spire':
            b.building(0,0,3.1,2.8,1.1,1,glass='glass_bronze')
            b.building(0,.12,2.20,2.1,8.7,1,1.2,glass='glass_teal')
            b.building(0,.12,1.60,1.55,2.5,1,9.9,glass='glass_teal')
            b.prism(0,.12,12.5,.80,.80,.50,'detail',.12,2)
            b.prism(0,.12,13.0,.11,.11,1.35,'detail',.015,2)
            b.screen(0,-.91,6.4,1.5)
        elif name=='stelander_twin':
            b.building(0,0,3.25,2.85,.95,2,glass='glass_silver')
            b.building(-.91,.14,1.22,2.00,10.8,1,1.05,glass='glass_bronze')
            b.building(.91,.14,1.22,2.00,8.80,1,1.05,glass='glass_teal')
            b.prism(0,.25,7.2,.8,.85,.5,'glass_silver')
            b.prism(0,.25,7.14,.86,.90,.08,'detail',.04,2)
            b.screen(-.91,-.84,8.8,1.05,1)
            b.screen(.91,-.84,5.4,1.05,2)
        else:
            b.building(-.90,.45,1.4,1.9,9.70,1,glass='glass_silver')
            b.building(.85,.45,1.35,1.9,7.80,1,glass='glass_teal')
            b.building(0,-.92,2.95,.85,3.55,2,glass='glass_bronze')
            b.prism(0,.47,5.40,3.3,2.30,.18,'concrete')
            b.prism(0,.47,5.58,3.05,2.05,.27,'glass_bronze')
            b.prism(-.9,.45,9.95,.72,.8,.35,'detail',.08,2)
            b.screen(0,-1.35,.82,1.85,3)
            b.garden(0,.5,.52,.8)
    else:
        b.plaza(7.4,6.3)
        if name=='quarter_business':
            rows=[(-2.30,1.5,1.35,1.40,2.85,1),(-.55,1.5,1.30,1.40,3.90,1),
                  (1.75,1.3,2.05,1.75,2.00,1),(-2.40,-1.7,1.20,1.8,1.7,2),
                  (-.85,-1.9,1.1,1.4,2.35,1),(1.15,-1.8,1.85,1.6,3.05,1),
                  (2.8,-1.8,.75,1.7,1.05,2)]
            b.prism(-1.45,1.5,2.05,.66,.5,.24,'glass')
            b.prism(1.55,.02,.07,2.4,.90,.28,'concrete')
            b.garden(1.6,.02,1.8,.52)
        elif name=='quarter_mixed':
            rows=[(-2.4,1.6,1.25,1.4,2.45,0),(-.75,1.6,1.25,1.4,1.55,0),
                  (1.7,1.5,2.30,1.6,2.05,2),(-2.5,-1.6,1.1,1.9,1.20,0),
                  (-.6,-1.8,1.9,1.55,2.8,1),(1.72,-1.6,1.65,1.9,1.5,0),
                  (2.9,0,.65,.7,.65,2)]
            b.garden(-.3,.25,.9,.42)
            b.garden(1.1,.25,.6,.42)
        else:
            rows=[(-2.3,1.7,1.4,1.35,2.20,0),(-.4,1.7,1.4,1.35,1.85,0),
                  (1.8,1.7,1.65,1.35,2.55,0),(-2.45,-1.65,1.10,1.8,1.45,0),
                  (-.78,-1.8,1.20,1.5,2.4,0),(.85,-1.8,1.2,1.5,1.6,0),
                  (2.5,-1.45,1.15,2.1,2.0,0)]
            for x in (-2.4,-.8,.8,2.4):
                b.garden(x,.05,.65,.58)
        for x,y,w,d,h,style in rows:
            b.building(x,y,w,d,h,style)
        if name=='quarter_business':b.screen(1.15,-2.58,1.2,1.1,2)
    if name in ('tower_admin','tower_business','tower_residential'):
        # Extra height belongs to the silhouette, while the buried foundation keeps its depth.
        b.vertices=[(x,y,z*1.45 if z>0 else z) for x,y,z in b.vertices]
    factor = .60 if name.startswith('quarter') else (.30 if name.startswith('stelander') else .40)
    # Keep the buried foundation depth independent from the visible skyline.
    b.vertices=[(x*factor,y*factor,z*factor if z>0 else z) for x,y,z in b.vertices]
    return b


def inspect(path):
    result=[]
    tree=pdx_data.read_meshfile(str(path))
    for shape in tree.find('object'):
        assert shape.find('skeleton') is None
        for mesh in shape.findall('mesh'):
            data=pdx_data.PDXData(mesh)
            n=len(data.p)//3
            assert 0<n<65536 and len(data.n)==n*3 and len(data.u0)==n*2
            assert all(math.isfinite(v) for v in data.p+data.n+data.u0+data.ta)
            assert len(data.tri)%3==0 and min(data.tri)>=0 and max(data.tri)<n
            points=[Vector(data.p[i:i+3]) for i in range(0,len(data.p),3)]
            areas=[(points[b]-points[a]).cross(points[c]-points[a]).length/2 for a,b,c in zip(data.tri[::3],data.tri[1::3],data.tri[2::3])]
            assert min(areas)>1e-9
            assert all(abs(Vector(data.n[i:i+3]).length-1)<.001 for i in range(0,len(data.n),3))
            assert data.material.shader==['PdxMeshAdvancedSnow']
            for key in ('diff','n','spec'):
                assert (ROOT/getattr(data.material,key)[0]).is_file()
            result.append({'vertices':n,'triangles':len(data.tri)//3,'material':data.material.diff[0],'minimum_triangle_area':min(areas)})
    return result


def foundation(path):
    points=[]
    for shape in pdx_data.read_meshfile(str(path)).find('object'):
        for mesh in shape.findall('mesh'):
            values=pdx_data.PDXData(mesh).p
            points.extend(zip(values[::3],values[1::3],values[2::3]))
    lower=min(p[1] for p in points)
    base=sorted({(round(x,6),round(z,6)) for x,y,z in points if abs(y-lower)<1e-5})
    def half(rows):
        hull=[]
        for p in rows:
            while len(hull)>1:
                a,b=hull[-2:]
                if (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])>1e-9:break
                hull.pop()
            hull.append(p)
        return hull[:-1]
    outline=half(base)+half(reversed(base))
    assert len(outline)==8, 'Expected the continuous chamfered plinth'
    upper=[]
    for x,z in outline:
        upper.append(min(y for xx,y,zz in points if abs(xx-x)<1e-5 and abs(zz-z)<1e-5 and y>lower+1e-5))
    assert max(upper)-min(upper)<1e-5
    return {'outline':outline,'lower':lower,'upper':min(upper),
            'mesh_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def landmark_geometry():
    landmarks={}
    for name,folder in (('factory','wasterland_special'),('reactor','wasterland_special'),
                        ('reactor_2','wasterland_special'),('congress','stelander_special')):
        path=MOD/f'gfx/models/buildings/{folder}/ADISCORD_{name}.mesh'
        points=[]
        for shape in pdx_data.read_meshfile(str(path)).find('object'):
            for mesh in shape.findall('mesh'):
                values=pdx_data.PDXData(mesh).p
                points.extend(zip(values[::3],values[1::3],values[2::3]))
        landmarks[name]={'path':path.relative_to(MOD).as_posix(),
                         'outline':convex_hull((p[0],p[2]) for p in points),
                         'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                         'minimum':[min(p[i] for p in points) for i in range(3)],
                         'maximum':[max(p[i] for p in points) for i in range(3)]}
    return landmarks


def studio(scene):
    scene.render.engine='CYCLES'
    scene.cycles.samples=24
    scene.render.resolution_x=1500
    scene.render.resolution_y=1400
    scene.render.resolution_percentage=100
    scene.world=bpy.data.worlds.new('City studio')
    scene.world.color=(.18,.18,.18)
    scene.view_settings.view_transform='AgX'
    target=Vector((0,6,4))
    bpy.ops.object.camera_add(location=(22,-44,35))
    camera=bpy.context.object
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO'
    camera.data.ortho_scale=40
    scene.camera=camera
    for loc,power in [((8,-15,30),17000),((-20,-3,16),9500),((0,22,22),16000)]:
        bpy.ops.object.light_add(type='AREA',location=loc)
        lamp=bpy.context.object
        lamp.data.energy=power
        lamp.data.size=20
        lamp.rotation_euler=(target-lamp.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.47))
    ground=bpy.context.object
    mat=bpy.data.materials.new('Studio ground')
    mat.diffuse_color=(.075,.09,.1,1)
    ground.data.materials.append(mat)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version=0
    mats=[]
    for name in MATERIALS:
        spec=SimpleNamespace(shader=['PdxMeshAdvancedSnow'],diff=[f'City_{name}_diffuse.dds'],
                             n=['City_screen_normal.dds' if name=='screen' else 'City_normal.dds'],spec=[f'City_{name}_specular.dds'])
        mat=pdx.create_shader(spec,'City_'+name,str(ROOT))
        preview_gloss(mat)
        mats.append(mat)
    report={}
    for index,name in enumerate(NAMES):
        obj=model(name).object(mats)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active=obj
        path=ROOT/f'ADISCORD_city_{name}.mesh'
        pdx.export_meshfile(str(path),exp_selected=True)
        report[name]={'parts':inspect(path),'size':list(obj.dimensions),'source_vertices':len(obj.data.vertices),
                      'foundation':foundation(path)}
        # Preview only exported and imported native geometry.
        bpy.data.objects.remove(obj,do_unlink=True)
        before=set(bpy.context.scene.objects)
        pdx.import_meshfile(str(path),join_materials=False)
        for native in set(bpy.context.scene.objects)-before:
            if native.type=='MESH':
                row=1 if index<3 else (0 if index<6 else 2)
                native.location=Vector(((index%3-1)*9.1,row*11,0))
                for material in native.data.materials:
                    preview_gloss(material)
    scene=bpy.context.scene
    studio(scene)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Vorkensberg_city.blend'))
    scene.render.filepath=str(ROOT/'City_native_preview.png')
    bpy.ops.render.render(write_still=True)
    report['landmarks']=landmark_geometry()
    (ROOT/'build_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))


if __name__=='__main__':
    if '--inspect-landmarks' in sys.argv:
        report=json.loads((ROOT/'build_report.json').read_text())
        landmarks=landmark_geometry()
        report['landmarks']=landmarks
        (ROOT/'build_report.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(landmarks))
    elif '--inspect' in sys.argv:
        report=json.loads((ROOT/'build_report.json').read_text())
        for name in NAMES:
            report[name]['foundation']=foundation(ROOT/f'ADISCORD_city_{name}.mesh')
        (ROOT/'build_report.json').write_text(json.dumps(report,indent=2))
        print(json.dumps({name:report[name]['foundation'] for name in NAMES}))
    else:
        main()
