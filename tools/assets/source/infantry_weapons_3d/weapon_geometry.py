"""Game silhouettes with open guards, hollow optics and vented handguards.

Dimensions preserve the existing native infantry grip/stock envelope. These
are visual props with fictional internals, not mechanical construction models.
"""
import bpy
import bmesh
import math
from mathutils import Vector


def build_geometry(level,box,profile,cylinder,finish,metal,edge,grip,furniture,lens,recess):
    def mesh(name,verts,faces,mat):
        data=bpy.data.meshes.new(name)
        data.from_pydata(verts,[],faces)
        bm=bmesh.new()
        bm.from_mesh(data)
        # Each helper creates one connected, closed component.
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bm.to_mesh(data)
        bm.free()
        data.update()
        obj=bpy.data.objects.new(name,data)
        bpy.context.scene.collection.objects.link(obj)
        return finish(obj,name,mat)

    def ring(name,y,z,outer,inner,length,mat,n=12):
        verts=[(r*math.cos(i*2*math.pi/n), yy, z+r*math.sin(i*2*math.pi/n))
               for yy in (y-length/2,y+length/2) for r in (outer,inner) for i in range(n)]
        faces=[]
        for i in range(n):
            j=(i+1)%n
            faces.extend([(i,j,2*n+j,2*n+i),(n+j,n+i,3*n+i,3*n+j),
                          (j,i,n+i,n+j),(2*n+i,2*n+j,3*n+j,3*n+i)])
        return mesh(name,verts,faces,mat)

    def beam(name,a,b,radius,mat,vertices=8,bone='weapon_root'):
        a,b=Vector(a),Vector(b)
        bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=(b-a).length,location=(a+b)/2)
        obj=bpy.context.object
        obj.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
        bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
        return finish(obj,name,mat,bone)

    def side_profile(name,outline,width,x,mat):
        obj=profile(name,outline,width,mat)
        obj.location.x=x
        return obj

    def screws(y_values,z=.43,x=.175):
        for side in (-1,1):
            for y in y_values:
                beam('Recessed receiver fastener',(side*x,y,z),(side*(x+.015),y,z),.028,edge,8)
                box('Fastener slot',(side*(x+.017),y,z),(.006,.029,.008),recess,0)

    # Stocks have separate shoulder pads, combs, hinges and sling attachment.
    if level==0:
        profile('Sculpted walnut stock',[(1.73,.34),(1.74,-.16),(1.36,-.19),(.53,.06),(.28,.15),
                (-2.38,.19),(-2.40,.34),(-1.08,.39),(.20,.32),(.64,.41),(1.31,.48)],.25,furniture)
        box('Steel butt plate',(0,1.745,.08),(.258,.042,.48),edge,.014)
        for side in (-1,1):
            side_profile('Carved wrist checkering',[(.55,.20),(.82,.18),(1.15,.29),(.86,.35)],.008,side*.13,grip)
            for i in range(6):
                box('Walnut grain inlay',(side*.128,1.35-i*.19,.27),(.006,.12,.008),furniture,0)
    elif level in (1,2):
        profile('Tapered fixed stock',[(.30,.47),(1.23,.43),(1.56,.53),(1.66,.02),(1.63,-.16),
                (1.29,-.18),(.83,.06),(.47,.19),(.30,.20)],.26,furniture)
        box('Shoulder pad',(0,1.665,.18),(.28,.065,.61),grip,.018)
        cylinder('Stock trunnion',(0,.36,.37),.13,.24,edge)
        screws((.43,1.43),.30,.139)
    else:
        cylinder('Exposed buffer tube',(0,.76,.40),.095,1.08,edge)
        profile('Adjustable stock shell',[(.76,.49),(1.38,.50),(1.58,.37),(1.55,-.13),
                (1.40,-.15),(1.37,.18),(.80,.29)],.29,furniture)
        beam('Open stock brace',(0,.50,.22),(0,1.40,-.035),.055,metal)
        box('Raised cheek pad',(0,1.09,.53),(.25,.63,.08),grip,.025)
        box('Stock adjustment latch',(0,1.00,.22),(.11,.29,.07),edge,.012)
        box('Textured shoulder pad',(0,1.60,.14),(.30,.09,.58),grip,.026)
        for z in (-.06,.03,.12,.21,.30):
            box('Shoulder traction',(0,1.65,z),(.25,.012,.023),edge,.004)
        screws((.64,1.40),.37,.153)
    for side in (-1,1):
        beam('Rear sling lug',(side*.12,1.40,-.06),(side*.18,1.40,-.06),.043,metal)

    if level==0:
        cylinder('Cylindrical service action',(0,-.49,.45),.112,1.23,metal)
        ring('Receiver rear collar',.09,.45,.12,.085,.11,edge)
        box('Open ejection recess',(.106,-.51,.47),(.018,.39,.092),recess,.01)
        box('Bolt through ejection port',(.118,-.50,.49),(.013,.34,.041),edge,.006,'bolt')
        beam('Swept bolt handle',(.08,-.25,.47),(.27,-.12,.30),.024,edge,bone='bolt')
        beam('Bolt handle knob',(.265,-.12,.30),(.32,-.12,.30),.056,grip,12,'bolt')
        box('Internal magazine floor',(0,-.76,.15),(.22,.51,.11),metal,.014)
    else:
        # Two shaped housings instead of a single rectangular receiver.
        upper=[(.30,.34),(.23,.55),(-.14,.61),(-1.13,.60),(-1.31,.47),(-1.28,.29),(-.20,.28)]
        profile('Forged upper receiver',upper,.29 if level<5 else .32,metal)
        lower=[(.24,.32),(.20,.13),(-.28,.10),(-.41,.20),(-.91,.19),(-1.01,.30),(-.95,.36)]
        profile('Contoured lower receiver',lower,.28,metal if level<4 else furniture)
        profile('Magazine well',[(-.39,.28),(-.43,.07),(-.95,.07),(-1.04,.26)],.29,metal)
        profile('Swept pistol grip',[(.17,.26),(-.07,.20),(.015,-.34),(.105,-.39),(.30,-.32)],.195,grip)
        for side in (-1,1):
            side_profile('Grip side insert',[(.10,.04),(.01,-.10),(.07,-.31),(.26,-.29)],.010,side*.11,furniture)
            for z in (-.10,-.18,-.26):
                box('Grip traction band',(side*.117,.13,z),(.010,.13,.018),metal,.003)
        box('Ejection port recess',(.160,-.59,.46),(.014,.56,.125),recess,.015)
        box('Bolt visible through port',(.170,-.64,.47),(.013,.36,.062),edge,.007,'bolt')
        box('Lower dust cover lip',(.174,-.62,.39),(.027,.55,.026),metal,.006)
        box('Charging slide',(-.166,-.41,.50),(.025,.38,.041),recess,.008)
        box('Charging handle',(-.21,-.33,.50),(.12,.065,.046),edge,.01,'bolt')
        for side in (-1,1):
            beam('Selector axle',(side*.14,.08,.28),(side*.175,.08,.28),.04,edge)
            side_profile('Selector lever',[(.075,.30),(.15,.32),(.18,.29),(.08,.26)],.018,side*.185,metal)
            beam('Magazine release',(side*.15,-.40,.22),(side*.18,-.40,.22),.032,edge)
        screws((-.99,-.17,.21),.43,.165 if level<5 else .184)

    # Open swept trigger guard and a curved, separate trigger.
    zbase=.06 if level==0 else -.03
    guard=[(0,.12,.19),(0,.10,zbase),(0,-.26,zbase-.025),(0,-.40,zbase+.06),(0,-.42,.22)]
    for a,b in zip(guard,guard[1:]):beam('Trigger guard',a,b,.025,metal)
    beam('Trigger upper',(0,-.12,.24),(0,-.17,.13),.021,edge)
    beam('Trigger tip',(0,-.17,.13),(0,-.13,.10),.020,edge)

    if level:
        # The forward sweep grows below the well; flutes follow the curved body.
        shift=.14 if level in (1,2) else .045
        magazine=[(-.46,.18),(-.90,.18),(-.92,-.12),(-1.00-shift,-.48),
                  (-.94-shift,-.62),(-.61-shift,-.62),(-.56,-.25)]
        profile('Curved detachable magazine',magazine,.235,edge if level<3 else furniture)
        profile('Magazine floorplate',[(-1.04-shift,-.51),(-1.02-shift,-.66),(-.59-shift,-.66),(-.57-shift,-.58)],.258,grip)
        for side in (-1,1):
            for i in range(3):
                y=-.58-i*.11
                beam('Formed magazine flute',(side*.121,y,-.07),(side*.121,y-shift-.045,-.49),.015,metal,6)
            if level>=3:
                side_profile('Magazine inspection window',[(-.67,-.17),(-.82,-.17),(-.85,-.40),(-.70,-.40)],.008,side*.124,recess)
                for z in (-.20,-.27,-.34):box('Witness marks',(side*.13,-.76,z),(.004,.08,.012),edge,0)

    end=-2.35 if level<4 else -2.51
    barrel_end=-3.55 if level==0 else (-3.29 if level<3 else -3.12)
    cylinder('Continuous barrel',(0,(-1.08+barrel_end)/2,.43),.057,abs(barrel_end+1.08),metal)
    if level==0:
        for y in (-2.23,-1.55):
            ring('Barrel retaining band',y,.32,.163,.133,.064,edge)
        profile('Leaf rear sight base',[(-.65,.55),(-1.12,.55),(-1.07,.61),(-.73,.63)],.10,metal)
        box('Adjustable sight leaf',(0,-.94,.64),(.08,.24,.023),edge,.003)
        beam('Front sight blade',(0,-3.36,.48),(0,-3.36,.66),.024,metal)
    elif level<3:
        profile('Tapered handguard',[(-1.11,.27),(-1.23,.19),(end+.10,.21),(end,.34),
                (end+.07,.51),(-1.21,.52)],.29,furniture)
        cylinder('Gas return housing',(0,-1.84,.57),.046,1.28,edge)
        for side in (-1,1):
            for i in range(5):
                side_profile('Forearm cooling recess',[(-1.35-i*.18,.39),(-1.46-i*.18,.39),
                             (-1.48-i*.18,.44),(-1.34-i*.18,.44)],.009,side*.149,recess)
        ring('Front handguard collar',end+.08,.39,.183,.135,.11,metal)
    else:
        # Small openings retain a continuous silhouette at strategy-game zoom.
        for y in (-1.19,end+.04):
            ring('Forearm end collar',y,.43,.172,.145,.085,metal,8)
        profile('Lower handguard shell',[(-1.15,.29),(end,.30),(end-.015,.40),(-1.15,.39)],.285,furniture)
        profile('Upper handguard shell',[(-1.15,.455),(end,.45),(end+.04,.575),(-1.15,.59)],.278,furniture)
        for side in (-1,1):
            for i in range(6):
                box('Small vent divider',(side*.139,-1.20-i*.215,.425),(.022,.068,.075),furniture,.008)
            box('Inset mounting strip',(side*.15,-1.57,.34),(.015,.50,.065),metal,.006)
            for y in (-1.40,-1.63,-1.84):
                box('Mounting slot',(side*.159,y,.34),(.006,.095,.022),recess,.003)
        box('Palm support',(0,-1.78,.28),(.22,.72,.04),grip,.014)
        box('Receiver top rail',(0,-1.17,.634),(.12,2.04,.034),metal,.004)
        for i in range(18):
            box('Accessory rail tooth',(0,-.22-i*.116,.660),(.15,.061,.019),metal,.003)
    if level:
        ring('Gas block',end-.13,.43,.113,.067,.15,edge)
        beam('Front sight post',(0,end-.13,.48),(0,end-.13,.77),.025,metal)
        for side in (-1,1):beam('Sight protective ear',(side*.078,end-.13,.61),(side*.06,end-.13,.78),.021,metal)
        box('Rear sight base',(0,.07,.63),(.19,.15,.08),metal,.008)
        ring('Rear aperture',.04,.735,.065,.029,.035,edge,10)

    muzzle_y=barrel_end-.16
    if level==4:
        ring('Suppressor shell',-3.00,.43,.135,.069,.65,metal,16)
        for y in (-2.70,-3.25):ring('Suppressor end ring',y,.43,.141,.065,.065,edge,16)
        muzzle_y=-3.29
    else:
        ring('Open muzzle brake',barrel_end-.06,.43,.094 if level<5 else .137,.047,.22,edge if level<5 else furniture,12)
        for side in (-1,1):
            box('Muzzle port',(side*(.084 if level<5 else .125),barrel_end-.07,.43),(.015,.11,.036),recess,.004)
    # Bore is recessed behind the real annular opening.
    cylinder('Recessed muzzle darkness',(0,muzzle_y+.05,.43),.046,.008,recess)

    if level==3:
        box('Reflex mount',(0,-.41,.745),(.17,.47,.06),metal,.008)
        for side in (-1,1):
            beam('Reflex open hood',(side*.105,-.47,.76),(side*.105,-.47,1.00),.023,metal)
        beam('Reflex hood bridge',(-.105,-.47,1.00),(.105,-.47,1.00),.023,metal)
        box('Thin reflex lens',(0,-.47,.91),(.17,.012,.145),lens,.015)
        cylinder('Reflex battery compartment',(0,-.22,.79),.069,.16,grip)
    elif level>=4:
        for y in (-.16,-.63):
            box('Optic riser',(0,y,.75),(.15,.14,.13),metal,.007)
            ring('Optic clamp',y,.91,.125,.09,.075,edge,12)
        ring('Optical tube',-.42,.91,.105,.077,.69,metal,16)
        ring('Objective hood',-.83,.91,.16,.131,.25,furniture if level>4 else metal,16)
        cylinder('Recessed objective glass',(0,-.91,.91),.130,.009,lens)
        ring('Eyepiece shroud',.01,.91,.126,.079,.17,grip,16)
        cylinder('Recessed ocular glass',(0,.045,.91),.078,.009,lens)
        beam('Elevation turret',(0,-.35,1.0),(0,-.35,1.15),.071,edge,12)
        beam('Windage turret',(.08,-.35,.91),(.19,-.35,.91),.064,edge,12)
        for y in (-.035,.00,.035):ring('Eyepiece knurl',y,.91,.135,.12,.010,edge,16)
    if level>=4:
        box('Compact rangefinder',(.191,-1.42,.51),(.095,.30,.135),metal,.02)
        box('Rangefinder lens',(.191,-1.574,.52),(.056,.010,.052),lens,.01)
        beam('Rangefinder dial',(.226,-1.33,.51),(.249,-1.33,.51),.033,edge,10)
    if level>=5:
        side_profile('Ceramic receiver cheek',[(-.28,.51),(-.35,.33),(-1.14,.34),(-1.08,.55)],.025,-.189,furniture)
        for y in (-.42,-.57,-.72,-.87):box('Service panel groove',(-.204,y,.43),(.008,.022,.10),recess,.002)
        box('Optic sensor saddle',(-.16,-.72,.92),(.12,.34,.18),furniture,.025)
        box('Sensor window',(-.16,-.895,.94),(.069,.009,.089),lens,.01)
        screws((-.40,-1.03),.51,.205)
    if level>=6:
        for y in (-1.27,-1.68,-2.09):
            ring('Segmented induction shroud',y,.43,.194,.176,.085,edge,8)
        for side in (-1,1):
            beam('Insulated power line',(side*.19,-1.10,.34),(side*.19,-2.33,.34),.016,grip)
            box('Power coupling',(side*.19,-1.05,.34),(.045,.10,.065),furniture,.009)
        box('Removable cell',(0,.72,.16),(.27,.40,.16),furniture,.025)
        box('Cell latch',(0,.83,.067),(.13,.11,.031),edge,.005)
    if level==7:
        side_profile('Integrated fire control fairing',[(-.15,.47),(-.24,.28),(-.76,.30),(-.88,.56),(-.32,.60)],.09,.22,furniture)
        box('Inset control screen',(.27,-.46,.44),(.007,.22,.082),recess,.006)
        for y in (-.39,-.45,-.51):box('Quiet status indicator',(.275,y,.455),(.004,.022,.015),lens,0)
        for y in (-1.39,-1.80,-2.21):
            box('Thermal plate spine',(0,y,.72),(.14,.17,.11),furniture,.022)
    return muzzle_y
