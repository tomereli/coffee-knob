"""Assemble the interactive simulator from the exported layout.

    python tools/knob_export.py coffee-knob.yaml > tools/layout.json
    python tools/build_sim.py tools/layout.json knob-sim.html

Geometry, fonts and colours come from the config via layout.json. Content
comes from this file, because it lives in lambdas the simulator cannot run.
Keep that split: the moment content and geometry are both invented here, the
simulator is a drawing again and it will flatter the design.
"""
import sys

TEMPLATE_HEAD = '''<title>Coffee Knob Simulator</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{--ink:#14110f;--ink2:#4a423c;--ink3:#8a7f76;--ground:#f2efec;
 --panel:#fff;--line:#ded7d0;--lm:#c8221f}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
 --ink:#efe9e4;--ink2:#b3a79e;--ink3:#7d726a;--ground:#141211;
 --panel:#1d1a18;--line:#332e2b;--lm:#e8433f}}
:root[data-theme="dark"]{--ink:#efe9e4;--ink2:#b3a79e;--ink3:#7d726a;
 --ground:#141211;--panel:#1d1a18;--line:#332e2b;--lm:#e8433f}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);padding:26px 18px 44px;
 font-family:"IBM Plex Mono",ui-monospace,monospace;line-height:1.55}
.shell{max-width:980px;margin:0 auto}
h1{font-size:20px;font-weight:500;margin:0 0 2px}
.sub{color:var(--ink3);font-size:13px;margin:0 0 24px;max-width:62ch}
.stage{display:flex;gap:30px;flex-wrap:wrap;align-items:flex-start}
.bezel{width:392px;height:392px;border-radius:50%;background:#171717;
 display:flex;align-items:center;justify-content:center;box-shadow:inset 0 0 0 1px #262626}
.glass{position:relative;width:360px;height:360px;border-radius:50%;
 background:#000;overflow:hidden}
.glass div,.glass svg{position:absolute;left:50%;top:50%;
 transform:translate(-50%,-50%);white-space:nowrap;
 font-family:Montserrat,system-ui,sans-serif;font-weight:500}
.ctl{display:flex;gap:7px;margin-top:16px;justify-content:center;flex-wrap:wrap}
button{font:inherit;font-size:13px;padding:9px 13px;border-radius:7px;
 border:1px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer}
button:hover{border-color:var(--ink3)}
button:focus-visible{outline:2px solid var(--lm);outline-offset:2px}
.side{flex:1 1 330px;min-width:300px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;
 padding:13px 15px;margin-bottom:12px}
.card h2{font-size:12px;font-weight:500;margin:0 0 9px;text-transform:uppercase;
 letter-spacing:.08em;color:var(--ink3)}
.row{display:flex;justify-content:space-between;gap:10px;font-size:13px;padding:2px 0}
.row span:last-child{color:var(--ink2);font-variant-numeric:tabular-nums}
.seg{display:flex;gap:5px;flex-wrap:wrap}
.seg button{flex:1 1 auto;font-size:12px;padding:6px 8px}
.seg button[aria-pressed=true]{background:var(--lm);border-color:var(--lm);color:#fff}
.flag{font-size:12px;padding:7px 9px;border-radius:6px;margin-top:8px;border:1px solid;
 white-space:normal}
.bad{color:var(--lm);border-color:var(--lm)}
.ok{color:var(--ink3);border-color:var(--line)}
</style>
<div class="shell">
<h1>Coffee knob simulator</h1>
<p class="sub">Every page, drawn from the geometry, fonts and colours exported straight out of coffee-knob.yaml. Text does not wrap and the glass clips at 360px, exactly as LVGL does.</p>
<div class="stage">
 <div>
  <div class="bezel"><div class="glass" id="g"></div></div>
  <div class="ctl">
   <button id="ccw">&#8630; turn</button><button id="tap">tap</button>
   <button id="hold">hold</button><button id="cw">turn &#8631;</button>
  </div>
 </div>
 <div class="side">
  <div class="card"><h2>showing</h2>
   <div class="row"><span>page</span><span id="pg"></span></div>
   <div class="row"><span>where</span><span id="ctx"></span></div>
   <div id="fit"></div></div>
  <div class="card"><h2>machine</h2><div class="seg" id="mach">
   <button data-s="off">standby</button><button data-s="heat">heating</button>
   <button data-s="on">ready</button></div></div>
  <div class="card"><h2>what is happening</h2><div class="seg" id="scene">
   <button data-v="idle">idle</button><button data-v="shot">pulling</button>
   <button data-v="wait">waiting</button><button data-v="result">result</button>
   <button data-v="clean">backflush</button></div></div>
  <div class="card"><h2>pre-infusion mode</h2><div class="seg" id="mode">
   <button data-m="0">disabled</button><button data-m="1">prebrew</button>
   <button data-m="2">preinfusion</button></div>
   <div class="row" style="margin-top:7px"><span>dead settings screens</span><span id="dead"></span></div></div>
  <div class="card"><h2>bean name</h2><div class="seg" id="bean">
   <button data-b="0">Timothy</button><button data-b="1">Timothy - House Blend</button>
   <button data-b="2">a very long bean name</button></div></div>
 </div>
</div></div>
<script>const LAYOUT='''

TEMPLATE_BODY = r''';
const P={};LAYOUT.pages.forEach(p=>P[p.id]=p.w);
const BEANS=["Timothy","Timothy - House Blend","a very long bean name"];
let page="page_main",card=0,cfg=0,edit=false,mode=0,bean=1,mach="on",
    scene="idle",rateStep=-1,steam=true,level=1,temp=89,ratio=1.95,tgt=25;
const CARDS=["page_main","page_result","page_grind","page_care","page_boil"];

function cfgItem(){
 const na=m=>mode!==m;
 return [
  {n:"STEAM BOILER",v:steam?"ON":"OFF",f:48,h:"tap to toggle",act:()=>steam=!steam},
  {n:"STEAM LEVEL",v:""+level,f:48,h:"tap to cycle 1-3",act:()=>level=level%3+1},
  {n:"COFFEE TEMP",v:temp.toFixed(1),f:48,h:edit?"turn to set, tap to save":"tap to adjust",e:1,t:d=>temp=Math.min(104,Math.max(85,temp+.5*d))},
  {n:"TARGET RATIO",v:"1:"+ratio.toFixed(2),f:48,h:edit?"turn to set, tap to save":"tap to adjust",e:1,t:d=>ratio=Math.min(3,Math.max(1.2,ratio+.05*d))},
  {n:"TARGET TIME",v:tgt<.5?"auto":tgt+"s",f:48,c:tgt<.5?"#C8913C":"#FFFFFF",h:tgt<.5?"following the grinder":(edit?"turn to 0 for auto":"tap to adjust"),e:1,t:d=>tgt=Math.min(45,Math.max(0,tgt+d))},
  {n:"BEANS",v:BEANS[bean],f:20,c:"#C8913C",h:edit?"turn to pick, tap to keep":"tap to change - HOLD to save",e:1,t:d=>bean=(bean+d+3)%3},
  {n:"PRE-INFUSION",v:["OFF","PREBREW","PREINFUSION"][mode],f:20,c:mode?"#1F8B4C":"#6A6A6A",h:"tap to cycle",act:()=>mode=(mode+1)%3},
  {n:"PRE-INF TIME",v:na(2)?"n/a":"8.0s",f:48,h:na(2)?"set mode to PREINFUSION":"tap to adjust",e:!na(2)},
  {n:"PREBREW ON",v:na(1)?"n/a":"3.0s",f:48,h:na(1)?"set mode to PREBREW":"tap to adjust",e:!na(1)},
  {n:"PREBREW OFF",v:na(1)?"n/a":"3.0s",f:48,h:na(1)?"set mode to PREBREW":"tap to adjust",e:!na(1)},
  {n:"BACKFLUSH",v:"CLEAN",f:48,h:"HOLD to start"},
  {n:"BACK",v:"",f:48,h:"tap to exit"}];
}

function content(){
 const it=cfgItem()[cfg];
 const st=mach==="on"?"READY":mach==="heat"?"HEATING":"STANDBY";
 const stc=mach==="on"?"#FFFFFF":mach==="heat"?"#FF7A7A":"#585858";
 const rate=["ESPRESSO","BALANCED","4 / 5"][Math.max(0,rateStep)];
 return {
  lbl_main_ready:{t:mach==="heat"?"ready 4:20":"",c:"#FF9A4A"},
  lbl_state:{t:st,c:stc},
  lbl_last:{t:"1:1.9   29 s   4/5",c:"#3FBF5A"},
  lbl_main_care:{t:"backflush soon",c:"#B0823A"},
  lbl_cfg_name:{t:it.n},lbl_cfg_value:{t:it.v,f:it.f,c:it.c||"#FFFFFF"},
  lbl_cfg_hint:{t:it.h},lbl_cfg_icon:{t:""},
  lbl_clean_head:{t:"MOVE THE PADDLE",c:"#E8A33D"},
  lbl_clean_big:{t:"12",c:"#FFFFFF"},lbl_clean_sub:{t:"seconds to arm"},
  lbl_res_when:{t:"today  08:14"},lbl_res_ratio:{t:"1 : 1.9",c:"#35C759"},
  lbl_res_gram:{t:"18.0 -> 34.2 g"},lbl_res_meta:{t:"29.0 / 25 s   PERFECT"},
  lbl_res_grind:{t:"GRIND 116   +3",c:"#C8913C"},
  lbl_res_rate:{t:rateStep<0?"hold to rate":rate,c:rateStep<0?"#8A7A55":"#FFFFFF"},
  lbl_res_step:{t:rateStep<0?"":["serve      1 / 3","taste      2 / 3","score      3 / 3"][rateStep]},
  lbl_gr_dose:{t:"18.0 g"},lbl_gr_setting:{t:"grind 116"},
  lbl_gr_meta:{t:"6.5 s  |  PERFECT"},lbl_gr_beans:{t:BEANS[bean],c:"#C8913C"},
  lbl_gr_roast:{t:"18d off roast - prime"},lbl_gr_ago:{t:"18h ago"},
  lbl_care_ago:{t:"3h ago",c:"#35C759"},lbl_care_shots:{t:"12 shots since clean"},
  lbl_care_water:{t:"917 flushes / 637 shots",c:"#585858"},
  lbl_bo_temp:{t:temp.toFixed(1)},lbl_bo_coffee:{t:"coffee ready"},
  lbl_bo_steam:{t:"steam "+(steam?"level "+level:"off")},
  lbl_shot_beans:{t:bean!==1?BEANS[bean]:"",c:"#C8913C"},
  lbl_shot_time:{t:scene==="wait"?"29.0":"12.4"},
  lbl_shot_unit:{t:scene==="wait"?"fetching from Mahlkonig..":"seconds",
                 c:scene==="wait"?"#C8913C":"#4A4A4A"},
  lbl_shot_hint:{t:scene==="wait"?"tap to leave":"hold to leave"}};
}

function ringCol(){return mach==="on"?"#E31E24":mach==="heat"?"#8E1116":"#242424";}
function prog(){return page==="page_shot"?(scene==="wait"?.72:.31):
                       page==="page_clean"?.18:.62;}
function arcPath(cx,cy,r,a0,a1,w,c){
 const R=d=>d*Math.PI/180,lf=(a1-a0)>180?1:0;
 const x0=cx+r*Math.cos(R(a0)),y0=cy+r*Math.sin(R(a0));
 const x1=cx+r*Math.cos(R(a1)),y1=cy+r*Math.sin(R(a1));
 return '<path d="M '+x0.toFixed(1)+' '+y0.toFixed(1)+' A '+r+' '+r+' 0 '+lf+
  ' 1 '+x1.toFixed(1)+' '+y1.toFixed(1)+'" fill="none" stroke="'+c+
  '" stroke-width="'+w+'"/>';
}

function draw(){
 const g=document.getElementById("g");g.innerHTML="";
 const cn=content();
 (P[page]||[]).forEach(w=>{
  if(w.in)return;
  let el;
  if(w.k==="label"){
   const o=cn[w.id]||{};const txt=o.t!==undefined?o.t:w.t;
   if(!txt)return;
   el=document.createElement("div");el.textContent=txt;
   el.style.fontSize=(o.f||w.f)+"px";el.style.color=o.c||w.c;
   el.style.marginLeft=w.x+"px";el.style.marginTop=w.y+"px";
  }else if(w.k==="obj"||w.k==="button"){
   el=document.createElement("div");
   let bc=w.id==="ring"?ringCol():w.bc;
   let bw=w.bw;
   if(w.id==="ring_cfg"&&edit){bc="#FFFFFF";bw=10;}
   el.style.cssText="width:"+w.w+"px;height:"+w.h+"px;border-radius:"+
    (w.r>=w.w/2?"50%":w.r+"px")+";border:"+bw+"px solid "+bc+
    ";background:"+(w.bg||"transparent")+";margin-left:"+w.x+
    "px;margin-top:"+w.y+"px";
  }else if(w.k==="arc"){
   const r=w.w/2-w.aw/2;
   el=document.createElementNS("http://www.w3.org/2000/svg","svg");
   el.setAttribute("width",w.w);el.setAttribute("height",w.w);
   el.style.marginLeft=w.x+"px";el.style.marginTop=w.y+"px";
   el.innerHTML='<circle cx="'+w.w/2+'" cy="'+w.w/2+'" r="'+r+
    '" fill="none" stroke="'+w.tc+'" stroke-width="'+w.aw+'"/>'+
    arcPath(w.w/2,w.w/2,r,-90,-90+360*prog(),w.aw,w.ic);
  }else if(w.k==="image"){
   el=document.createElement("div");
   el.style.cssText="width:124px;height:60px;border-radius:6px;"+
    "background:#1a0507;border:1px solid #3a0d10;margin-left:"+w.x+
    "px;margin-top:"+w.y+"px";
  }
  if(el)g.appendChild(el);
 });
 status(cn);
}

function status(cn){
 document.getElementById("pg").textContent=page.replace("page_","");
 document.getElementById("ctx").textContent=
  page==="page_cfg"?("item "+(cfg+1)+" of 12"+(edit?" · editing":"")):
  (page==="page_result"&&rateStep>=0)?("rating step "+(rateStep+1)+" of 3"):
  ("card "+(card+1)+" of 5");
 let worst=null;
 (P[page]||[]).forEach(w=>{
  if(w.k!=="label"||w.in)return;
  const o=cn[w.id]||{};const txt=o.t!==undefined?o.t:w.t;if(!txt)return;
  const s=document.createElement("span");
  s.style.cssText="position:absolute;visibility:hidden;white-space:nowrap;"+
   "font-family:Montserrat,sans-serif;font-weight:500;font-size:"+(o.f||w.f)+"px";
  s.textContent=txt;document.body.appendChild(s);
  const px=s.getBoundingClientRect().width;s.remove();
  const av=2*Math.sqrt(Math.max(1,172*172-Math.pow(Math.abs(w.y)+(o.f||w.f)/2,2)));
  if(px>av&&(!worst||px-av>worst.over))worst={id:w.id,px:px,av:av,over:px-av};
 });
 const f=document.getElementById("fit");
 f.className="flag "+(worst?"bad":"ok");
 f.textContent=worst?(worst.id+" is "+Math.round(worst.px)+"px wide, only "+
  Math.round(worst.av)+"px of glass at that height — it runs off the edge")
  :"every label on this page fits the glass";
 let d=0;cfgItem().forEach(x=>{if(x.v==="n/a")d++;});
 document.getElementById("dead").textContent=d+" of 12";
 [["mach","s",mach],["scene","v",scene],["mode","m",String(mode)],
  ["bean","b",String(bean)]].forEach(function(a){
  document.querySelectorAll("#"+a[0]+" button").forEach(b=>
   b.setAttribute("aria-pressed",String(b.dataset[a[1]]===a[2])));});
}

function turn(d){
 if(page==="page_cfg"){
  const it=cfgItem()[cfg];
  if(edit&&it.t)it.t(d);else if(!edit)cfg=(cfg+d+12)%12;
 }else if(page!=="page_shot"&&page!=="page_clean"&&
          !(page==="page_result"&&rateStep>=0)){
  card=(card+d+5)%5;page=CARDS[card];
 }
 draw();
}
document.getElementById("cw").onclick=()=>turn(1);
document.getElementById("ccw").onclick=()=>turn(-1);
document.getElementById("tap").onclick=function(){
 if(page==="page_cfg"){
  const it=cfgItem()[cfg];
  if(it.n==="BACK"){edit=false;page="page_main";card=0;}
  else if(it.act)it.act();else if(it.e)edit=!edit;
 }else if(page==="page_result"&&rateStep>=0){
  rateStep=rateStep>=2?-1:rateStep+1;
 }else if(page==="page_main"){page="page_cfg";cfg=0;edit=false;}
 else{page="page_main";card=0;}
 draw();
};
document.getElementById("hold").onclick=function(){
 if(page==="page_result"&&rateStep<0)rateStep=0;
 else{edit=false;rateStep=-1;page="page_main";card=0;}
 draw();
};
document.querySelectorAll("#mach button").forEach(b=>
 b.onclick=()=>{mach=b.dataset.s;draw();});
document.querySelectorAll("#mode button").forEach(b=>
 b.onclick=()=>{mode=+b.dataset.m;draw();});
document.querySelectorAll("#bean button").forEach(b=>
 b.onclick=()=>{bean=+b.dataset.b;draw();});
document.querySelectorAll("#scene button").forEach(b=>b.onclick=function(){
 scene=b.dataset.v;rateStep=-1;
 page=(scene==="shot"||scene==="wait")?"page_shot":
      scene==="clean"?"page_clean":scene==="result"?"page_result":"page_main";
 card=page==="page_result"?1:0;
 draw();});
addEventListener("keydown",function(e){
 if(e.key==="ArrowRight"){turn(1);e.preventDefault();}
 if(e.key==="ArrowLeft"){turn(-1);e.preventDefault();}});
draw();
</script>'''


def main(layout_path, out_path):
    layout = open(layout_path, encoding='utf-8').read().strip()
    html = TEMPLATE_HEAD + layout + TEMPLATE_BODY
    open(out_path, 'w', encoding='utf-8', newline='').write(html)
    print('wrote %s (%d bytes)' % (out_path, len(html)))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
