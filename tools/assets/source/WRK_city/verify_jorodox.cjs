/* Verify static geometry and full texture chains with the installed JoroDox loaders. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const toolRoot=process.argv[2];
assert(toolRoot,'Pass the installed JoroDox extension folder');
const modRoot=path.resolve(__dirname,'../../../..');
const modelRoot=path.join(modRoot,'gfx/models/buildings/ADISCORD_city');
const buffer=file=>{const b=fs.readFileSync(file);return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);};
const warnings=[],pending=[],services={};
const dependencies={
 $rootScope:{},$filter:()=>v=>v,
 $q:{defer(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {resolve,reject,promise};}},
 modService:{getFileBuffer(file){const promise=Promise.resolve(buffer(file));pending.push(promise);return promise;}}
};
const context=vm.createContext({console:{log:(...v)=>warnings.push(v.join(' ')),warn:(...v)=>warnings.push(v.join(' '))},
 angular:{module:()=>({factory(name,spec){services[name]=spec.at(-1)(...spec.slice(0,-1).map(k=>dependencies[k]));}})},setTimeout,clearTimeout});
context.self=context;
for(const file of ['bower_components/three.js/three.min.js','bower_components/DDSLoader/index.js','js/pdxDataService.js','js/rendererService.js'])
 vm.runInContext(fs.readFileSync(path.join(toolRoot,file),'utf8'),context,{filename:file});
async function main(){
 const report={tool:'JoroDox Tools',version:JSON.parse(fs.readFileSync(path.join(toolRoot,'manifest.json'))).version,meshes:{}};
 for(const file of fs.readdirSync(modelRoot).filter(n=>n.endsWith('.mesh'))){
  const tree=services.pdxDataService.readFromBuffer(buffer(path.join(modelRoot,file)));
  const view=await services.rendererService.loadPdxMesh(tree,modelRoot.replaceAll('\\','/'));
  await Promise.all(pending);
  assert(view.meshes.length>=4 && view.meshes.length<=7);
  report.meshes[file]=view.meshes.map(mesh=>{
   assert(mesh.geometry.vertices.every(v=>[v.x,v.y,v.z].every(Number.isFinite)));
   for(const kind of ['map','normalMap','specularMap']){
    const t=mesh.material[kind];
    assert(t && t.mipmaps.length>=9);
    assert.equal(t.mipmaps.at(-1).width,1);assert.equal(t.mipmaps.at(-1).height,1);
   }
   return {vertices:mesh.geometry.vertices.length,triangles:mesh.geometry.faces.length,
    textures:['map','normalMap','specularMap'].map(k=>mesh.material[k].fileName)};
  });
 }
 assert.equal(Object.keys(report.meshes).length,9);
 report.warnings=[...new Set(warnings)];
 report.limitations=['JoroDox previews PdxMeshAdvancedSnow with a Phong fallback; this does not prove native snow, lighting or ambient height.'];
 fs.writeFileSync(path.join(__dirname,'jorodox_report.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify({meshes:Object.keys(report.meshes).length,status:'PASS',warnings:report.warnings}));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
