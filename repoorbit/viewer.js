(async () => {
'use strict';
const dataset=document.getElementById('dataset');
let D;
if(dataset.dataset.encoding==='gzip-base64'){
  if(typeof DecompressionStream!=='function')throw new Error('This browser does not support offline gzip decompression. Regenerate with --html-format plain.');
  const binary=atob(dataset.textContent.trim());
  const bytes=Uint8Array.from(binary,c=>c.charCodeAt(0));
  const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
  D=JSON.parse(await new Response(stream).text());
}else{
  D=JSON.parse(dataset.textContent);
}
if (D.packed === 'path-index-v1') {
  const paths = D.paths;
  D.baseline = D.baseline.map(id => paths[id]);
  D.top_paths = D.top_paths.map(([id, n]) => [paths[id], n]);
  for (const c of D.commits) {
    c.versions = c.changes.map(row => row[2]);
    c.changes = c.changes.map(([code, id]) => [code, paths[id]]);
  }
  delete D.paths;
  delete D.packed;
} else if (D.packed !== undefined) {
  throw new Error('Unsupported REPO ORBIT payload format');
}
const $ = id => document.getElementById(id);
const orbit = $('orbit'), ctx = orbit.getContext('2d');
const activity = $('activity'), act = activity.getContext('2d');
const scrub = $('scrub'), search = $('search'), tooltip = $('hover');
const nframes = D.commits.length;
const fileNames = new Set(D.baseline);
for (const commit of D.commits) for (const [, path] of commit.changes) fileNames.add(path);
const files = [...fileNames].sort();
// One normalized name per path; filtered draws reuse a precomputed membership mask.
const fileNamesLower = files.map(path => path.toLowerCase());
const index = new Map(files.map((p, i) => [p, i]));
const root = p => p.includes('/') ? p.split('/')[0] : '(root)';
const groups = [...new Set(files.map(root))].sort();
const groupIndex = new Map(groups.map((g, i) => [g, i]));
const nodeGroups = files.map(root);
const categories = {code:'#79f2cc', docs:'#b6a7ff', asset:'#f8d090'};
const codeRE = /\.(?:py|js|jsx|ts|tsx|rs|go|c|cpp|cc|h|hpp|java|kt|rb|php|cs|swift|sh|sql|css|html|vue|svelte|dart|scala|lua|zig|code)$/i;
const docsRE = /\.(?:md|mdx|rst|txt|adoc|pdf|tex|docs)$/i;
const kind = p => codeRE.test(p) ? 'code' : docsRE.test(p) ? 'docs' : 'asset';
const fileKinds = files.map(kind);
const hash = s => { let h=2166136261; for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}return h>>>0; };
const seeds = files.map(hash);
// Version IDs preserve exact (Git object ID + file mode) equality, not a touch heuristic.
const changeIndex = D.commits.map(c => c.changes.map(([code, path], i) => [code, index.get(path), c.versions[i]]));
const histories = new Map();
changeIndex.forEach((row, frame) => row.forEach(([code, id]) => {
  if (!histories.has(id)) histories.set(id, []);
  histories.get(id).push({frame, code});
}));
const initial = new Uint32Array(files.length);
D.baseline.forEach((path, i) => { initial[index.get(path)] = D.baseline_versions[i]; });
// Bound browser checkpoint memory to about 64 snapshots at large history sizes.
// Seeking still replays exact object versions from the nearest checkpoint.
const checkpointStride = Math.max(32, Math.ceil(nframes / 64));
const checkpoints = new Map([[-1, initial.slice()]]);
let snapshot = initial.slice();
// Constant-time tracked-file count, with no 12,000-node scan per frame/repaint.
const fileCounts = [initial.reduce((n, version) => n + (version !== 0 ? 1 : 0), 0)];
changeIndex.forEach((row, i) => {
  let count = fileCounts[i];
  for (const [code, id, version] of row) {
    if (!snapshot[id] && version) count++;
    else if (snapshot[id] && !version) count--;
    snapshot[id] = version;
  }
  fileCounts.push(count);
  if (i % checkpointStride === checkpointStride-1 || i === nframes-1) checkpoints.set(i, snapshot.slice());
});
let active = initial.slice(), frame = -1, hot = new Map(), selected = null, hovered = null;
let mode = 'orbit', filterGroup = '', query = '', zoom = 1, panX = 0, panY = 0;
let pinFrame = null, pinSnapshot = null, comparison = null;
let playing = false, speedIdx = 0, lastFrameTime = 0, motion = 0, showGrowth = true;
const speeds = [1, 4, 16, 64, 256];
let width = 1, height = 1, dpr = 1, coords = [], paintQueued = false, pulse = 0;
// The spatial search index depends on static layout, not the current Git frame.
// Build it at the first pointer query and reuse it across all frame changes.
// Pointer queries invert zoom/pan, so the index needs rebuilding only on resize.
const spatialCell = 26;
let spatialIndexes = {orbit:null, atlas:null}, pointerDown = null;
let densityScratch = null;
function spatialIndex(view) {
  if (spatialIndexes[view]) return spatialIndexes[view];
  const bins = new Map();
  for (let id=0; id<coords.length; id++) {
    const p = coords[id][view];
    const key = `${Math.floor(p.x/spatialCell)},${Math.floor(p.y/spatialCell)}`;
    let members = bins.get(key);
    if (!members) { members=[]; bins.set(key,members); }
    members.push(id);
  }
  spatialIndexes[view]=bins;
  return bins;
}
const nf = n => Number(n).toLocaleString('en-US');
const date = d => {if(!d)return 'Date redacted';const x=new Date(d);return Number.isNaN(+x) ? String(d).slice(0,10) : x.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});};
const titleFrame = i => i < 0 ? 'Baseline' : `Commit ${i+1}`;
// Select only matching paths once per search/group change. Ordinary redraws,
// animation, pan and zoom then operate in O(matches) instead of O(all files).
// The mask preserves O(1) visibility checks for exact pointer hit testing.
let visibleIDs = null, visibleMask = null;
function rebuildVisible() {
  if (!query && !filterGroup) {visibleIDs=null;visibleMask=null;return;}
  const ids=[], mask=new Uint8Array(files.length);
  for(let id=0;id<files.length;id++) {
    if(query && !fileNamesLower[id].includes(query))continue;
    if(filterGroup && nodeGroups[id]!==filterGroup)continue;
    ids.push(id);mask[id]=1;
  }
  visibleIDs=ids;visibleMask=mask;
}
const visible = id => !visibleMask || visibleMask[id]===1;
const N = () => fileCounts[frame+1];
const el = (tag, cls, value) => { const node=document.createElement(tag);if(cls)node.className=cls;if(value!==undefined)node.textContent=value;return node; };
const matchPanel = $('matchpanel'), matchCount = $('matchcount'), matches = $('matches');
// Search is not only a canvas filter: the bounded result list is keyboard and
// screen-reader accessible. All labels are assigned through textContent.
function renderMatches() {
  matches.replaceChildren();
  matchPanel.hidden = !query;
  if (!query) return;
  let count = 0;
  for (const id of visibleIDs || []) {
    count++;
    if (count > 24) continue;
    const button = el('button', 'match-button', files[id]);
    button.type = 'button';
    button.setAttribute('aria-label', `Inspect file ${files[id]}`);
    button.addEventListener('click', () => {
      pause();
      const history = histories.get(id) || [];
      if (!active[id] && history.length) jump(history[history.length-1].frame);
      choose(id);
      $('inspectpath').scrollIntoView({behavior:'auto',block:'nearest'});
    });
    matches.append(button);
  }
  matchCount.textContent = count
    ? `Showing ${Math.min(count,24)} of ${nf(count)} matching files` : 'No matching files';
}
// Hotspot explorer: most frequently changed tracked files in the selected window.
const hotspotPanel = $('hotspots');
if (D.top_paths.length === 0) hotspotPanel.append(el('p','empty','No changed paths in this window.'));
D.top_paths.forEach(([path, count], rank) => {
  const button=el('button','hotspot-button');button.type='button';
  button.setAttribute('aria-label', `Inspect hotspot ${path}`);
  button.append(el('span','hotspot-rank',`${rank+1}`),el('span','hotspot-path',path),el('span','hotspot-count',`${nf(count)} events`));
  button.addEventListener('click',()=>{
    const id=index.get(path);if(id===undefined)return;
    pause();const h=histories.get(id)||[];
    jump(h.length?h[h.length-1].frame:-1);choose(id);
    $('inspectpath').scrollIntoView({behavior:'smooth',block:'nearest'});
  });
  hotspotPanel.append(button);
});
$('statcommits').textContent=nf(nframes);
  $('statcoverage').textContent=`${nframes} / ${D.history_total} first-parent commits · ${D.verified_frames} verified`;
$('statchanges').textContent=nf(D.changes_total);
$('statauthors').textContent=nf(new Set(D.commits.map(c=>c.author)).size);
$('datawarning').textContent = D.share_safe
  ? 'REDACTED · Names/dates removed; structure and object-equivalence patterns can still identify a project.'
  : 'SHARE WITH CARE · Original paths, author names, commit messages and dates remain.';
scrub.max=String(nframes);
for (const group of groups) {const o=el('option','',group);o.value=group;$('groupfilter').append(o);}
function schedule() { if (!paintQueued && !document.hidden) {paintQueued=true;requestAnimationFrame(draw);} }
function jump(next) {
  const to=Math.max(-1,Math.min(nframes-1,next));
  if(to === frame) return;
  if(to === frame+1) {
    for(const [,id,version] of changeIndex[to]) active[id]=version;
  } else {
    const base=Math.floor((to+1)/checkpointStride)*checkpointStride-1;
    const checkpoint=Math.max(-1,Math.min(to,base));
    active=(checkpoints.get(checkpoint) || initial).slice();
    for(let i=checkpoint+1;i<=to;i++) for(const [,id,version] of changeIndex[i]) active[id]=version;
  }
  frame=to;
  hot=new Map(to>=0?changeIndex[to].map(([code,id])=>[id,code]):[]);
  pulse=.8;
  comparison=null;
  $('compare').classList.remove('active');
  update();
}
function update() {
  const c=frame<0?null:D.commits[frame];
  $('statfiles').textContent=nf(N());
  scrub.value=String(frame+1);
  $('timeposition').textContent=`FRAME ${frame+1} / ${nframes}`;
  $('timedate').textContent=c?date(c.date):'Before the selected window';
  $('eventtitle').textContent=c?c.subject:'The starting constellation';
  $('eventauthor').textContent=c?c.author:'Initial tracked Git tree';
  $('eventdate').textContent=c?date(c.date):'Before selected history';
  $('eventsha').textContent=c?c.sha.slice(0,12):'BASELINE';
  $('changehead').textContent=c?`${nf(c.changes.length)} FILE CHANGES`:'INITIAL STATE';
  const list=$('events');list.replaceChildren();
  if(!c || !c.changes.length) list.append(el('p','empty',c?'No file changes in this commit.':`${nf(D.baseline.length)} existing files before this history window.`));
  else {
    for(const [status,path] of c.changes.slice(0,100)) {
      const row=el('div','event '+(status==='D'?'deleted':status==='A'?'added':'modified'));
      const button=el('button','event-button');button.type='button';button.setAttribute('aria-label',`Inspect ${path}`);
      button.append(el('span','letter',status),el('span','event-path',path));
      button.addEventListener('click',()=>choose(index.get(path)));
      row.append(button);list.append(row);
    }
    if(c.changes.length>100) list.append(el('p','empty',`+ ${nf(c.changes.length-100)} more changes in this frame.`));
  }
  $('compare').disabled = pinFrame === null;
  if(pinFrame!==null) $('diffmeta').textContent=`A: ${pinFrame+1} · B: ${frame+1}`;
  if(selected!==null) updateInspector();
  drawActivity();schedule();
}
function choose(id) {
  if(!Number.isInteger(id))return;
  selected=id; updateInspector(); schedule();
}
function updateInspector() {
  if(selected===null)return;
  const h=histories.get(selected)||[];
  $('inspectpath').textContent=files[selected];
  $('inspectcount').textContent=`${nf(h.length)} events`;
  const panel=$('inspectevents');panel.replaceChildren();
  panel.append(el('span','',`Status in frame: ${active[selected]?'tracked':'absent'} · Category: ${fileKinds[selected]}`));
  for(const ev of h.slice(-8).reverse()) {
    const b=el('button','btn',`${ev.code} · ${titleFrame(ev.frame)} · ${date(D.commits[ev.frame].date)}`);
    b.style.margin='5px 6px 0 0';b.addEventListener('click',()=>{pause();jump(ev.frame);});
    panel.append(b);
  }
}
function pinA() {
  pinFrame=frame;pinSnapshot=active.slice();comparison=null;
  $('pinA').textContent=`◆ A = ${frame+1}`;$('pinA').classList.add('active');
  $('compare').disabled=false;
  $('compare').classList.remove('active');
  $('diffsummary').textContent=`Snapshot A pinned at frame ${frame+1}. Move to a different frame, then compare.`;
  $('diffdetails').textContent='Comparison uses exact Git object identity and file mode, never raw source bytes.';
  $('diffmeta').textContent=`A: ${frame+1} · B: —`;
  drawActivity(); schedule();
}
function compare() {
  if(pinSnapshot===null)return;
  // Equality of opaque identifiers is equivalent to equality of Git object+mode.
  let added=0,removed=0,modified=0;
  const changes=new Map(), examples=[];
  for(let i=0;i<files.length;i++){
    let code=null;
    if(!pinSnapshot[i]&&active[i]){code='A';added++;}
    else if(pinSnapshot[i]&&!active[i]){code='D';removed++;}
    else if(pinSnapshot[i]&&active[i]&&pinSnapshot[i]!==active[i]){code='M';modified++;}
    if(code){changes.set(i,code);if(examples.length<12)examples.push(`${code} ${files[i]}`);}
  }
  comparison=changes;
  $('compare').classList.add('active');
  $('diffmeta').textContent=`A: ${pinFrame+1} · B: ${frame+1}`;
  $('diffsummary').textContent=`${nf(added)} added · ${nf(removed)} removed · ${nf(modified)} changed between frames`;
  $('diffdetails').textContent=(examples.length?examples.join(' · '):'No observed file-status differences.')+
     (modified?' · Equality is based on Git object identity and file mode.':' · No net object/mode changes in remaining files.');
  pulse=.5;schedule();
}
function resize() {
  const b=orbit.getBoundingClientRect();width=Math.max(1,b.width);height=Math.max(1,b.height);
  dpr=Math.min(window.devicePixelRatio||1,2);
  orbit.width=Math.round(width*dpr);orbit.height=Math.round(height*dpr);
  ctx.setTransform(dpr,0,0,dpr,0,0);
  const cx=width*.5,cy=height*.53,r=Math.min(width*.38,height*.35);
  const columns=Math.max(1,Math.ceil(Math.sqrt(files.length * (width-75)/(height-95))));
  const rows=Math.max(1,Math.ceil(files.length/columns));
  const atlasX=Math.max(1,(width-90)/columns), atlasY=Math.max(1,(height-115)/rows);
  const groupCounts=new Map(),groupPositions=[];
  coords=files.map((path,i)=>{
    const g=nodeGroups[i],gi=groupIndex.get(g),n=groupCounts.get(g)||0;groupCounts.set(g,n+1);
    const a=groups.length<2?-Math.PI/2:(gi/groups.length)*Math.PI*2-Math.PI/2;
    const gx=cx+Math.cos(a)*r*.74,gy=cy+Math.sin(a)*r*.74;
    const theta=(seeds[i]/4294967296)*Math.PI*2+n*2.3999632297;
    const radius=Math.sqrt((n+.5)/(n+8))*Math.min(100,r*.57);
    const orbitPoint={x:gx+Math.cos(theta)*radius,y:gy+Math.sin(theta)*radius};
    const gridPoint={x:45+(i%columns+.5)*atlasX,y:60+(Math.floor(i/columns)+.5)*atlasY};
    if(!groupPositions[gi])groupPositions[gi]={x:gx,y:gy};
    return {orbit:orbitPoint,atlas:gridPoint};
  });
  resize.groupPositions=groupPositions;
  spatialIndexes = {orbit:null, atlas:null};
  densityScratch = null;
  const bar=activity.getBoundingClientRect();activity.width=Math.round(bar.width*dpr);activity.height=Math.round(bar.height*dpr);
  act.setTransform(dpr,0,0,dpr,0,0);
  drawActivity();schedule();
}
function project(point) {
  return {x:width*.5+(point.x-width*.5)*zoom+panX,y:height*.5+(point.y-height*.5)*zoom+panY};
}
// Draw at most one activity bar per on-screen pixel. Preserve the most
// intense commit per pixel and sample the actual file-count trajectory.
const activityPeak = Math.max(1, ...D.commits.map(c => c.changes.length));
const growthPeak = Math.max(1, ...fileCounts);
function drawActivity() {
  const w=activity.getBoundingClientRect().width,h=activity.getBoundingClientRect().height;
  act.clearRect(0,0,w,h);
  if(!nframes)return;
  const columns=Math.max(1,Math.ceil(w));
  for(let x=0;x<columns;x++) {
    const first=Math.floor(x*nframes/columns);
    const last=Math.max(first+1,Math.floor((x+1)*nframes/columns));
    let highest=0;
    for(let i=first;i<last;i++)highest=Math.max(highest,D.commits[i].changes.length);
    const barH=4+Math.log1p(highest)/Math.log1p(activityPeak)*40;
    // The current-frame boundary is drawn separately, so zoomed-out bars
    // use their end-frame status without changing underlying data.
    act.fillStyle=last-1<=frame?'#79f2cc':'#35495a';
    act.fillRect(x,h-5-barH,Math.max(.8,w/columns),barH);
  }
  if(showGrowth) {
    act.strokeStyle='#77d6ff';act.lineWidth=2;act.beginPath();
    for(let x=0;x<=columns;x++) {
      const idx=Math.min(nframes,Math.round(x*nframes/columns));
      const y=5+(1-fileCounts[idx]/growthPeak)*(h-13);
      if(x===0)act.moveTo(0,y);else act.lineTo(x*w/columns,y);
    }
    act.stroke();
  }
  if(pinFrame!==null){act.fillStyle='#ffdb8a';act.fillRect(((pinFrame+1)/nframes)*w-1,0,2,h);}
  act.fillStyle='#79f2cc66';act.fillRect(((frame+1)/nframes)*w-1,0,2,h);
}

function draw(t) {
  paintQueued=false;
  ctx.clearRect(0,0,width,height);
  const cx=width*.5,cy=height*.5;
  const bg=ctx.createRadialGradient(cx,cy,0,cx,cy,Math.max(width,height)*.72);
  bg.addColorStop(0,'#203b4f');bg.addColorStop(.55,'#0f1c2b');bg.addColorStop(1,'#080f19');
  ctx.fillStyle=bg;ctx.fillRect(0,0,width,height);
  if(mode==='orbit') {
    ctx.strokeStyle='#30495b';ctx.lineWidth=.75;
    for(const r of [.18,.32,.45]){ctx.beginPath();ctx.ellipse(cx+panX,cy+panY,
      Math.min(width,height)*r*1.28*zoom,Math.min(width,height)*r*zoom,0,0,Math.PI*2);ctx.stroke();}
  } else {
    ctx.strokeStyle='#172f3c';ctx.lineWidth=.7;
    for(let x=40;x<width;x+=44){ctx.beginPath();ctx.moveTo(x,43);ctx.lineTo(x,height-38);ctx.stroke();}
  }
  // High-density mode avoids tens of thousands of Canvas arc+fill operations.
  // Underlying exact point coordinates and hover/inspection remain available.
  const densityMode=files.length>12000 && zoom<=1.8 && !query && !filterGroup;
  let bins=null;
  if (densityMode) {
    // Screen-space density aggregation uses compact flat counters rather than
    // 80,000 string-key Map lookups and short-lived per-pixel objects.
    const cols=Math.ceil(width/5)+8, rows=Math.ceil(height/5)+8;
    if(!densityScratch || densityScratch.cols!==cols || densityScratch.rows!==rows){
      const cells=cols*rows;
      densityScratch={cols,rows,code:new Uint32Array(cells),docs:new Uint32Array(cells),
        asset:new Uint32Array(cells),delta:new Uint8Array(cells),touched:[]};
    }
    bins=densityScratch;
    for(const index of bins.touched){
      bins.code[index]=bins.docs[index]=bins.asset[index]=0;
      bins.delta[index]=0;
    }
    bins.touched.length=0;
  }
  let filtered=0;
  const drawable=visibleIDs, drawableLength=drawable?drawable.length:files.length;
  for(let row=0;row<drawableLength;row++){
    const i=drawable?drawable[row]:row;
    const exist=active[i], difference=comparison&&comparison.get(i);
    if(!exist && difference!=='D')continue;
    const src=coords[i][mode];
    const x=cx+(src.x-cx)*zoom+panX, y=cy+(src.y-cy)*zoom+panY;
    if(x<-15||x>width+15||y<-15||y>height+15)continue;
    filtered++;
    if(densityMode) {
      const cell=(Math.floor(y/5)+4)*bins.cols+(Math.floor(x/5)+4);
      if(!bins.code[cell]&&!bins.docs[cell]&&!bins.asset[cell])bins.touched.push(cell);
      bins[fileKinds[i]][cell]++;
      const priority=difference==='D'?3:difference==='M'?2:difference==='A'?1:0;
      if(priority>bins.delta[cell])bins.delta[cell]=priority;
      continue;
    }
    let color=categories[fileKinds[i]],radius=1.9;
    if(difference==='A'){color='#79f2cc';radius=3.3;}
    if(difference==='D'){color='#ff8aa9';radius=3.3;}
    if(difference==='M'){color='#70cfff';radius=3.1;}
    if(hot.has(i))radius=3.2;
    ctx.globalAlpha=difference==='D'?.8:.87;
    ctx.fillStyle=color;ctx.beginPath();ctx.arc(x,y,radius,0,Math.PI*2);ctx.fill();
    if(hot.has(i)||difference==='D'){
      ctx.strokeStyle=hot.get(i)==='D'||difference==='D'?'#ff8aa9':'#89ffd8';
      ctx.globalAlpha=.40+pulse*.46;ctx.lineWidth=1;
      ctx.beginPath();ctx.arc(x,y,radius+4+pulse*4,0,Math.PI*2);ctx.stroke();
    }
    if(selected===i||hovered===i){
      ctx.globalAlpha=1;ctx.strokeStyle=selected===i?'#fff':'#7ce8ff';ctx.lineWidth=1.5;
      ctx.beginPath();ctx.arc(x,y,9,0,Math.PI*2);ctx.stroke();
    }
  }
  if(densityMode){
    ctx.globalAlpha=.93;
    for(const cell of bins.touched){
      const code=bins.code[cell],docs=bins.docs[cell],asset=bins.asset[cell];
      ctx.fillStyle=bins.delta[cell]===3?'#ff8aa9':bins.delta[cell]===2?'#70cfff':
        docs>code&&docs>=asset?categories.docs:
        asset>code&&asset>docs?categories.asset:categories.code;
      const count=code+docs+asset;
      const side=Math.min(5,1.3+Math.log2(count+1));
      const bx=cell%bins.cols-4,by=Math.floor(cell/bins.cols)-4;
      ctx.fillRect(bx*5+(5-side)/2,by*5+(5-side)/2,side,side);
    }
    // Prioritize precisely selected/hovered files over density aggregation.
    for(const id of [selected,hovered]){
      if(id===null||!active[id]||!visible(id))continue;
      const point=project(coords[id][mode]);
      ctx.globalAlpha=1;ctx.strokeStyle=id===selected?'#ffffff':'#7ce8ff';
      ctx.lineWidth=1.6;ctx.beginPath();ctx.arc(point.x,point.y,10,0,Math.PI*2);ctx.stroke();
    }
  }
  ctx.globalAlpha=1;
  if(mode==='orbit'&&groups.length<=18) {
    ctx.textAlign='center';ctx.font='600 10px ui-monospace,Consolas,monospace';ctx.fillStyle='#8eaabc';
    (resize.groupPositions||[]).forEach((p,i)=>{
      if(!p||filterGroup&&groups[i]!==filterGroup)return;
      const pos=project(p);
      ctx.fillText(groups[i].length>14?groups[i].slice(0,13)+'…':groups[i],pos.x,pos.y+75*zoom);
    });
  }
  ctx.font='11px ui-monospace,Consolas,monospace';ctx.fillStyle='#7096ab';ctx.textAlign='center';
  ctx.fillText(`${nf(filtered)} VISIBLE NODES  ·  ${densityMode?'DENSITY OVERVIEW · ZOOM FOR DETAIL':mode==='orbit'?'CONSTELLATION':'FOLDER ATLAS'}`,cx,Math.max(42,cy-5));
  $('frameinfo').textContent=comparison?'COMPARING SNAPSHOTS':`${nf(N())} TRACKED FILES`;
  if(pulse>.01&&!window.matchMedia('(prefers-reduced-motion: reduce)').matches){pulse*=.89;schedule();}else pulse=0;
}
function nearest(mx,my) {
  const sx=(mx-width*.5-panX)/zoom+width*.5;
  const sy=(my-height*.5-panY)/zoom+height*.5;
  const index=spatialIndex(mode);
  const bx=Math.floor(sx/spatialCell), by=Math.floor(sy/spatialCell);
  // Pixel hit radius is invariant under zoom. Search the corresponding
  // untransformed neighborhoods so selection stays exact after pan/zoom.
  const reach=Math.ceil(Math.sqrt(95)/zoom/spatialCell)+1;
  let winner=null, min=95;
  for(let dx=-reach;dx<=reach;dx++)for(let dy=-reach;dy<=reach;dy++){
    for(const id of index.get(`${bx+dx},${by+dy}`)||[]){
      if(!active[id] && !(comparison&&comparison.get(id)==='D'))continue;
      if((query||filterGroup) && !visible(id))continue;
      const p=coords[id][mode];
      const x=width*.5+(p.x-width*.5)*zoom+panX;
      const y=height*.5+(p.y-height*.5)*zoom+panY;
      if(x<-15||x>width+15||y<-15||y>height+15)continue;
      const r=(x-mx)**2+(y-my)**2;
      if(r<min){min=r;winner=id;}
    }
  }
  return winner;
}
function pause() {playing=false;$('play').textContent='▶';$('play').setAttribute('aria-label','Play evolution');}
function toggle() {
  if(playing){pause();return;}
  if(frame>=nframes-1)jump(-1);
  playing=true;$('play').textContent='Ⅱ';$('play').setAttribute('aria-label','Pause evolution');
  lastFrameTime=0;motion=0;requestAnimationFrame(tick);
}
function tick(t){
  if(!playing)return;
  if(!lastFrameTime)lastFrameTime=t;
  motion += Math.min(120,t-lastFrameTime)*speeds[speedIdx]/450;
  lastFrameTime=t;
  if(motion>=1){
    const step=Math.floor(motion);motion-=step;
    if(frame>=nframes-1){pause();return;}
    jump(Math.min(nframes-1,frame+step));
  }
  requestAnimationFrame(tick);
}

function resetZoom(){zoom=1;panX=0;panY=0;schedule();}
function zoomAround(mx,my,factor) {
  const next=Math.max(.55,Math.min(5,zoom*factor));
  const ratio=next/zoom;
  panX+=(mx-width*.5-panX)*(1-ratio);
  panY+=(my-height*.5-panY)*(1-ratio);
  zoom=next;schedule();
}
function download(name,blob) {
  const a=document.createElement('a');const url=URL.createObjectURL(blob);
  a.download=name;a.href=url;document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),2000);
}
// Two deliberately distinct SVG formats:
// overview = bounded density aggregation, exact = one path-aware element per file.
// Neither export contains repository source bytes. Exact SVG does contain file paths.
// XML 1.0 rejects most C0 control characters even in escaped text nodes.
// Git permits such characters in filenames, so replace them before escaping.
const xmlText = text => String(text)
  .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffe\uffff]/g, '\ufffd')
  .replace(/[&<>\"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&apos;'}[c]));
function svgExport(exact=false){
  const dense = !exact && files.length > 12000 && zoom <= 1.8 && !query && !filterGroup;
  const parts=[`<svg xmlns="http://www.w3.org/2000/svg" width="${Math.round(width)}" height="${Math.round(height)}" viewBox="0 0 ${width} ${height}">`,
    `<title>REPO ORBIT · ${xmlText(D.name)} · frame ${frame+1}/${nframes}</title>`,
    `<rect width="${width}" height="${height}" fill="#0d1a27"/>`,
    `<text x="24" y="27" fill="#bfe9ee" font-size="13" font-family="sans-serif">REPO ORBIT · ${xmlText(D.name)} · FRAME ${frame+1}/${nframes}${dense?' · DENSITY OVERVIEW':''}</text>`];
  let included=0;
  if(dense){
    // At overview scales, export the same density composition used on Canvas.
    // This prevents tens of thousands of SVG nodes in a shareable visual.
    // Category counts and a sum invariant make the aggregation auditable.
    const bins=new Map(), cellSize=5;
    for(let id=0;id<files.length;id++){
      const difference=comparison && comparison.get(id);
      if(!active[id] && difference!=='D')continue;
      const p=project(coords[id][mode]);
      if(p.x<-15||p.x>width+15||p.y<-15||p.y>height+15)continue;
      const x=Math.floor(p.x/cellSize),y=Math.floor(p.y/cellSize),key=`${x},${y}`;
      let bin=bins.get(key);
      if(!bin){bin={x,y,code:0,docs:0,asset:0,delta:null};bins.set(key,bin);}
      bin[fileKinds[id]]++;included++;
      if(difference==='D'||(difference==='M'&&bin.delta!=='D')||(!bin.delta&&difference==='A'))bin.delta=difference;
    }
    for(const bin of bins.values()){
      const count=bin.code+bin.docs+bin.asset;
      const color=bin.delta==='D'?'#ff8aa9':bin.delta==='M'?'#70cfff':
        bin.docs>bin.code&&bin.docs>=bin.asset?categories.docs:
        bin.asset>bin.code&&bin.asset>bin.docs?categories.asset:categories.code;
      const side=Math.min(5,1.3+Math.log2(count+1));
      parts.push(`<rect x="${(bin.x*5+(5-side)/2).toFixed(2)}" y="${(bin.y*5+(5-side)/2).toFixed(2)}" width="${side.toFixed(2)}" height="${side.toFixed(2)}" fill="${color}" data-count="${count}"/>`);
    }
    parts.push(`<desc>Aggregated density overview; ${included} visible nodes represented by ${bins.size} cells. Zoom or select SVG exact to retain per-file elements. Cell counts do not disclose filenames.</desc>`);
  } else {
    const candidates=visibleIDs, count=candidates?candidates.length:files.length;
    for(let row=0;row<count;row++){
      const id=candidates?candidates[row]:row;
      if(!active[id])continue;
      const p=project(coords[id][mode]);if(p.x<0||p.y<0||p.x>width||p.y>height)continue;
      included++;
      parts.push(`<circle cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="${id===selected?4:2}" fill="${categories[fileKinds[id]]}"><title>${xmlText(files[id])}</title></circle>`);
    }
    parts.push(`<desc>Exact per-file SVG: ${included} independently inspectable path elements. Original paths may be disclosed.</desc>`);
  }
  parts.push('</svg>');
  // Blob(parts) avoids a huge live SVG DOM tree and XMLSerializer traversal.
  download(`repo-orbit-frame-${frame+1}-${dense?'overview':'exact'}.svg`,new Blob(parts,{type:'image/svg+xml;charset=utf-8'}));
}
$('play').addEventListener('click',toggle);
$('reset').addEventListener('click',()=>{pause();jump(-1);});
$('speed').addEventListener('click',()=>{speedIdx=(speedIdx+1)%speeds.length;$('speed').textContent=`${speeds[speedIdx]}× speed`;});
$('growth').addEventListener('click',()=>{showGrowth=!showGrowth;$('growth').classList.toggle('active',showGrowth);$('growth').setAttribute('aria-pressed',String(showGrowth));drawActivity();});
scrub.addEventListener('input',()=>{pause();jump(Number(scrub.value)-1);});
$('viewmode').addEventListener('click',()=>{mode=mode==='orbit'?'atlas':'orbit';$('viewmode').textContent=mode==='orbit'?'◈ Atlas view':'◎ Constellation view';$('viewlabel').textContent=mode==='orbit'?'◉ CONSTELLATION / FILE UNIVERSE':'▦ ATLAS / FILE UNIVERSE';resetZoom();});
$('groupfilter').addEventListener('change',e=>{filterGroup=e.target.value;rebuildVisible();hovered=null;renderMatches();schedule();});
search.addEventListener('input',e=>{query=e.target.value.toLowerCase().trim();rebuildVisible();hovered=null;tooltip.style.display='none';renderMatches();schedule();});
$('pinA').addEventListener('click',pinA);
$('compare').addEventListener('click',compare);
$('zoomreset').addEventListener('click',resetZoom);
$('export').addEventListener('click',()=>{
  orbit.toBlob(b=>{if(b)download(`repo-orbit-frame-${frame+1}.png`,b);},'image/png');
});
$('exportsvg').addEventListener('click',()=>svgExport(false));
$('exportsvgexact').addEventListener('click',()=>svgExport(true));
orbit.addEventListener('wheel',e=>{e.preventDefault();const r=orbit.getBoundingClientRect();zoomAround(e.clientX-r.left,e.clientY-r.top,e.deltaY<0?1.13:.88);},{passive:false});
orbit.addEventListener('dblclick',resetZoom);
orbit.addEventListener('pointerdown',e=>{if(e.button!==0)return;pointerDown={x:e.clientX,y:e.clientY,panX,panY,dragged:false};orbit.setPointerCapture(e.pointerId);});
orbit.addEventListener('pointermove',e=>{
  const r=orbit.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
  if(pointerDown){
    const dx=e.clientX-pointerDown.x,dy=e.clientY-pointerDown.y;
    if(Math.hypot(dx,dy)>5)pointerDown.dragged=true;
    if(pointerDown.dragged){panX=pointerDown.panX+dx;panY=pointerDown.panY+dy;tooltip.style.display='none';schedule();return;}
  }
  const next=nearest(mx,my);
  if(hovered!==next){hovered=next;schedule();}
  if(next===null){tooltip.style.display='none';return;}
  tooltip.style.display='block';tooltip.textContent=files[next];
  tooltip.style.left=Math.max(8,Math.min(width-260,mx+12))+'px';
  tooltip.style.top=Math.max(40,Math.min(height-85,my-35))+'px';
});
orbit.addEventListener('pointerup',e=>{
  if(!pointerDown)return;
  if(!pointerDown.dragged){const r=orbit.getBoundingClientRect();const found=nearest(e.clientX-r.left,e.clientY-r.top);if(found!==null)choose(found);}
  pointerDown=null;
});
orbit.addEventListener('pointercancel',()=>{pointerDown=null;});
orbit.addEventListener('pointerleave',()=>{hovered=null;tooltip.style.display='none';schedule();});
document.addEventListener('keydown',e=>{
  if(e.altKey||e.ctrlKey||e.metaKey||e.target.closest('input,button,select,textarea'))return;
  if(e.code==='Space'&&!e.repeat){e.preventDefault();toggle();}
  if(e.code==='ArrowRight'){e.preventDefault();pause();jump(frame+1);}
  if(e.code==='ArrowLeft'){e.preventDefault();pause();jump(frame-1);}
});
window.addEventListener('resize',resize);
document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();else schedule();});
resize();update();schedule();
})().catch(error=>{
  const message=document.getElementById('datawarning');
  if(message)message.textContent='DATA ERROR · '+String(error.message||error).slice(0,180);
  throw error;
});
