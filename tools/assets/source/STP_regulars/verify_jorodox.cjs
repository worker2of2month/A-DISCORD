/* Use JoroDox's installed parser, scene loader and DDS loader independently of Blender. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');

const toolRoot = process.argv[2];
assert(toolRoot, 'Pass the JoroDox extension directory containing manifest.json');
const sourceRoot = __dirname;
const modRoot = path.resolve(sourceRoot, '../../../..');
const gameRoot = process.argv[3] || 'Z:/SteamLibrary/steamapps/common/Hearts of Iron IV';
const warnings = [];
const services = {};
const textures = [];
const buffer = file => {
    const data = fs.readFileSync(file);
    return data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength);
};
const deps = {
    $rootScope: {},
    $q: {defer() {
        let resolve, reject;
        const promise = new Promise((yes, no) => {resolve = yes; reject = no;});
        return {resolve, reject, promise};
    }},
    modService: {getFileBuffer(file) {
        const promise = Promise.resolve(buffer(file));
        textures.push(promise);
        return promise;
    }},
    $filter: () => value => value,
};
const context = vm.createContext({
    console: {log: (...items) => warnings.push(items.join(' ')), warn: (...items) => warnings.push(items.join(' '))},
    angular: {module: () => ({factory(name, definition) {
        services[name] = definition.at(-1)(...definition.slice(0, -1).map(key => deps[key]));
    }})},
    setTimeout, clearTimeout,
});
context.self = context;
const sources = ['bower_components/three.js/three.min.js', 'bower_components/DDSLoader/index.js',
                 'js/pdxDataService.js', 'js/rendererService.js'];
for (const file of sources) vm.runInContext(fs.readFileSync(path.join(toolRoot,file),'utf8'), context, {filename:file});
const pdx = services.pdxDataService;
const renderer = services.rendererService;

async function main() {
    const report = {tool: 'JoroDox Tools', version: JSON.parse(fs.readFileSync(path.join(toolRoot,'manifest.json'))).version,
        sourceHashes: Object.fromEntries(sources.map(file => [file, crypto.createHash('sha256').update(fs.readFileSync(path.join(toolRoot,file))).digest('hex')])),
        models: {}, warnings};
    const registry = fs.readFileSync(path.join(modRoot, 'gfx/entities/ADISCORD_country_infantry.gfx'), 'utf8');
    const nativeAnimations = new Map([...fs.readFileSync(path.join(gameRoot, 'gfx/models/units/animation.asset'), 'utf8')
        .matchAll(/animation\s*=\s*\{\s*name\s*=\s*"([^"]+)"\s*file\s*=\s*"([^"]+)"/g)]
        .map(match => [match[1], match[2]]));
    for (const match of registry.matchAll(/\bpdxmesh\s*=\s*\{([\s\S]*?)(?=\bpdxmesh\s*=|$)/g)) {
        const block = match[1];
        const meshFile = block.match(/\bfile\s*=\s*"([^"]+)"/)[1];
        if (!/^gfx\/models\/units\/(STP_shabrat|ADISCORD_regulars)\//.test(meshFile)) continue;
        const label = path.basename(meshFile, '.mesh');
        const nativeRoot = path.dirname(path.join(modRoot, meshFile));
        const tree = pdx.readFromBuffer(buffer(path.join(modRoot, meshFile)));
        const view = await renderer.loadPdxMesh(tree, nativeRoot.replaceAll('\\','/'));
        await Promise.all(textures);
        const parts = view.meshes.map(mesh => {
            const geometry = mesh.geometry;
            assert.equal(geometry.skinIndices.length, geometry.vertices.length);
            assert.equal(geometry.skinWeights.length, geometry.vertices.length);
            assert(geometry.vertices.every(v => [v.x,v.y,v.z].every(Number.isFinite)));
            for (const kind of ['map','normalMap','specularMap']) {
                const texture = mesh.material[kind];
                assert(texture && texture.mipmaps.length >= 10,
                    `${label}: ${kind} missing/incomplete; material=${mesh.material.name}; warnings=${warnings.join('; ')}`);
                assert.equal(texture.mipmaps.at(-1).width,1);
                assert.equal(texture.mipmaps.at(-1).height,1);
            }
            return {vertices: geometry.vertices.length, triangles: geometry.faces.length,
                bones: mesh.skeleton.bones.length, textures: ['map','normalMap','specularMap'].map(k => mesh.material[k].fileName)};
        });
        const bones = new Set(tree.props.object.subNodes[0].props.skeleton.subNodes.map(b=>b.name));
        const animations = {};
        for (const mapping of block.matchAll(/animation\s*=\s*\{\s*id\s*=\s*"([^"]+)"\s*type\s*=\s*"([^"]+)"/g)) {
            const [, action, type] = mapping;
            assert(nativeAnimations.has(type), `Unresolved animation ${type}`);
            const animFile = nativeAnimations.get(type);
            const anim = pdx.readFromBuffer(buffer(path.join(gameRoot, 'gfx/models/units', animFile)));
            const animBones = anim.props.info.subNodes.filter(n => n.type === 'object');
            assert(animBones.every(b=>bones.has(b.name)), action + ': missing rig bone');
            assert(Object.values(anim.props.samples.props).flat().every(Number.isFinite));
            animations[action] = {file:animFile, samples:anim.props.info.props.sa, fps:anim.props.info.props.fps, bones:animBones.length};
        }
        assert.equal(Object.keys(animations).length, 23, label + ': incomplete animation registry');
        report.models[label] = {parts, animations};
    }
    assert.equal(Object.keys(report.models).length, 4, 'Expected militia and three regular bodies');
    const weaponRoot=path.join(modRoot,'gfx/models/units/ADISCORD_weapons');
    report.weapons={};
    if (fs.existsSync(weaponRoot)) for (let level=0;level<8;level++) {
        const name=`infantry_${level}`;
        const tree=pdx.readFromBuffer(buffer(path.join(weaponRoot,name+'.mesh')));
        const view=await renderer.loadPdxMesh(tree,weaponRoot.replaceAll('\\','/'));
        await Promise.all(textures);
        assert.equal(view.meshes.length,1);
        const mesh=view.meshes[0];
        assert.equal(mesh.skeleton.bones.length,2);
        assert.equal(mesh.geometry.skinIndices.length,mesh.geometry.vertices.length);
        for(const key of ['map','normalMap','specularMap']) {
            assert.equal(mesh.material[key].mipmaps.length,10);
            assert.equal(mesh.material[key].mipmaps.at(-1).width,1);
        }
        const bones=new Set(mesh.skeleton.bones.map(b=>b.name));
        const clips={};
        for (const suffix of ['fire','support','idle']) {
            const anim=pdx.readFromBuffer(buffer(path.join(weaponRoot,name+'_'+suffix+'.anim')));
            assert.equal(anim.props.info.props.sa,79);
            const animBones=anim.props.info.subNodes.filter(n=>n.type==='object');
            assert.equal(animBones.length,2);
            assert(animBones.every(b=>bones.has(b.name)));
            assert(Object.values(anim.props.samples.props).flat().every(Number.isFinite));
            clips[suffix]={samples:79,fps:anim.props.info.props.fps};
        }
        report.weapons[name]={vertices:mesh.geometry.vertices.length,triangles:mesh.geometry.faces.length,
            bones:2,clips};
    }
    const towerRoot=path.join(modRoot,'gfx/models/buildings/ADISCORD_unity_tower');
    if (fs.existsSync(towerRoot)) {
        const towerSpec=JSON.parse(fs.readFileSync(path.join(sourceRoot,'../WRK_unity_tower/build_report.json'),'utf8'));
        const tree=pdx.readFromBuffer(buffer(path.join(towerRoot,'ADISCORD_unity_tower_destruction.mesh')));
        const view=await renderer.loadPdxMesh(tree,towerRoot.replaceAll('\\','/'));
        await Promise.all(textures);
        assert.equal(view.meshes.length,towerSpec.mesh.length);
        for (const mesh of view.meshes) {
            assert.equal(mesh.skeleton.bones.length,towerSpec.bones);
            assert(mesh.geometry.vertices.every(v=>[v.x,v.y,v.z].every(Number.isFinite)));
            for (const key of ['map','normalMap','specularMap']) {
                assert.equal(mesh.material[key].mipmaps.at(-1).width,1);
                assert.equal(mesh.material[key].mipmaps.at(-1).height,1);
            }
        }
        const bones=new Set(view.meshes[0].skeleton.bones.map(b=>b.name));
        const clips={};
        for (const [name,frames] of [['collapse',361],['ruins',31]]) {
            const anim=pdx.readFromBuffer(buffer(path.join(towerRoot,`ADISCORD_unity_tower_${name}.anim`)));
            const channels=anim.props.info.subNodes.filter(n=>n.type==='object');
            assert.equal(anim.props.info.props.sa,frames);
            assert(channels.every(b=>bones.has(b.name)));
            assert(Object.values(anim.props.samples.props).flat().every(Number.isFinite));
            clips[name]={frames,bones:channels.length};
        }
        report.unityTower={parts:view.meshes.length,bones:towerSpec.bones,clips};
    }
    report.warnings = [...new Set(warnings)];
    report.limitations = ['JoroDox does not implement the HOI4 PdxMeshAdvanced shader; its material preview uses Phong.',
        'Animation channel names and sample counts were read by JoroDox; visual pose validation is performed by Blender.',
        'No native HOI4 runtime result is implied.'];
    fs.writeFileSync(path.join(sourceRoot,'jorodox_report.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report,null,2));
}
main().catch(error => {console.error(error);process.exitCode=1;});
