const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib');
const roots=process.argv.slice(2);if(roots.length!==2)throw Error('Provide baseline and final build directories');
const routes=['/page','/c/[channel]/page','/a/[slug]/page'];
const asyncSizes=[];
const builds=roots.map(root=>{const dir=path.join(root,'.next');const loadable=JSON.parse(fs.readFileSync(path.join(dir,'react-loadable-manifest.json')));const lazy=[...new Set(Object.values(loadable).flatMap(entry=>entry.files))].filter(file=>file.endsWith('.js'));asyncSizes.push(lazy.reduce((n,file)=>n+zlib.gzipSync(fs.readFileSync(path.join(dir,file))).length,0)/1024);const manifest=JSON.parse(fs.readFileSync(path.join(dir,'app-build-manifest.json'))).pages;return routes.map(route=>{const files=[...new Set([...manifest['/layout'],...manifest[route]])].filter(file=>file.endsWith('.js'));return files.reduce((n,file)=>n+zlib.gzipSync(fs.readFileSync(path.join(dir,file))).length,0)/1024})});
const rows=routes.map((route,i)=>({route,beforeKiB:+builds[0][i].toFixed(2),afterKiB:+builds[1][i].toFixed(2),addedKiB:+(builds[1][i]-builds[0][i]).toFixed(2),beforeTotalKiB:+(builds[0][i]+asyncSizes[0]).toFixed(2),afterTotalKiB:+(builds[1][i]+asyncSizes[1]).toFixed(2),totalAddedKiB:+(builds[1][i]+asyncSizes[1]-builds[0][i]-asyncSizes[0]).toFixed(2)}));
console.table(rows);fs.writeFileSync(path.join(__dirname,'../design-review/motion-js.json'),JSON.stringify(rows,null,2));

if(rows[2].totalAddedKiB>35)throw Error('Article exceeds +35 KiB total gzip budget');
