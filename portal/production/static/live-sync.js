/* Shared live coordinator: one request at a time, no hidden-tab polling or edit loss. */
(()=>{'use strict';
window.SevlinkLiveSync={start({read,update,interval=2000}){
 let revision=null,timer,busy=false,dirty=true,stopped=false,retry=interval;
 const schedule=(delay=interval)=>{clearTimeout(timer);if(!stopped)timer=setTimeout(tick,delay);};
 async function tick(){
  clearTimeout(timer);if(stopped)return;
  if(document.hidden||busy){schedule();return;}
  busy=true;
  try{
   const data=await read();
   if(stopped)return;
   const force=dirty;dirty=false;
   if((revision!==null&&revision!==data.revision)||force){
    const applied=await update();
    if(applied===false){dirty=true;}else revision=data.revision;
   }else revision=data.revision;
   retry=interval;
  }catch(_){retry=Math.min(Math.max(retry*2,interval),30000);}
  finally{busy=false;schedule(dirty?interval:retry);}
 }
 function nudge(broadcast=true){dirty=true;schedule(100);if(broadcast){try{localStorage.setItem('sevlink-live-change',JSON.stringify({at:Date.now(),nonce:Math.random()}));}catch(_){}}}
 const visible=()=>{if(!document.hidden)nudge(false);};
 const storage=event=>{if(event.key==='sevlink-live-change')nudge(false);};
 document.addEventListener('visibilitychange',visible);window.addEventListener('focus',visible);window.addEventListener('online',visible);window.addEventListener('storage',storage);
 schedule(0);
 return {nudge,stop(){stopped=true;clearTimeout(timer);document.removeEventListener('visibilitychange',visible);window.removeEventListener('focus',visible);window.removeEventListener('online',visible);window.removeEventListener('storage',storage);}};
}};
})();
