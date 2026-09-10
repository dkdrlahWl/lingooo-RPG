from pathlib import Path
from html.parser import HTMLParser
import hashlib
import subprocess
import tempfile

# Apply only to the exact current main version. No game/account data is accessed.
path = Path('index.html')
original = path.read_bytes()
def blob(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
assert blob(original) == 'bf02aed89d91b771c2d50fcf5d61e837f26e13d7', 'Source changed; refusing to overwrite'
text = original.decode('utf-8')
def replace(before, after):
    global text
    assert text.count(before) == 1, 'Patch anchor missing or ambiguous'
    text = text.replace(before, after, 1)

input_code = """/* RINGU SHOP INPUT V2: one click opens the shop; actions need a new gesture. */
let shopInputEpoch=0,shopInputPointer=null,shopInputKey=null;
function resetShopInput(){shopInputEpoch++;shopInputPointer=null;shopInputKey=null}
(function bindShopInput(){
  const modal=$('auraShopModal');
  if(!modal)return;
  const pointerEvents=typeof window.PointerEvent==='function';
  const buttonAt=target=>target&&target.closest?target.closest('#auraShopModal button'):null;
  const isOpen=()=>modal.classList.contains('show');
  const stop=event=>{event.preventDefault();event.stopImmediatePropagation()};
  const pointerId=event=>pointerEvents?event.pointerId:0;
  function down(event){
    shopInputPointer=null;shopInputKey=null;
    const button=buttonAt(event.target);
    if(!isOpen()||!button||button.disabled||event.button!==0||event.isPrimary===false)return;
    shopInputPointer={button,epoch:shopInputEpoch,id:pointerId(event),x:event.clientX,y:event.clientY,released:false,cancelled:false};
  }
  function move(event){
    const input=shopInputPointer;
    if(!input||input.id!==pointerId(event)||input.released)return;
    if(Math.hypot(event.clientX-input.x,event.clientY-input.y)>12)input.cancelled=true;
  }
  function up(event){
    const input=shopInputPointer;
    if(!input||input.id!==pointerId(event))return;
    move(event);
    const rect=input.button.getBoundingClientRect();
    input.cancelled=input.cancelled||buttonAt(event.target)!==input.button||event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom;
    input.released=true;input.releasedAt=performance.now();
  }
  window.addEventListener(pointerEvents?'pointerdown':'mousedown',down,true);
  window.addEventListener(pointerEvents?'pointermove':'mousemove',move,true);
  window.addEventListener(pointerEvents?'pointerup':'mouseup',up,true);
  if(pointerEvents)window.addEventListener('pointercancel',()=>{shopInputPointer=null},true);
  window.addEventListener('blur',()=>{shopInputPointer=null;shopInputKey=null});
  modal.addEventListener('scroll',()=>{shopInputPointer=null},true);
  window.addEventListener('keydown',event=>{
    const button=buttonAt(event.target);
    if(!isOpen()||!button||!['Enter',' '].includes(event.key))return;
    if(event.repeat){stop(event);return}
    shopInputPointer=null;
    shopInputKey={button,epoch:shopInputEpoch};
  },true);
  window.addEventListener('click',event=>{
    const button=buttonAt(event.target);
    if(!button)return;
    const input=shopInputPointer,key=shopInputKey;
    // Consume before an action can replace the button or open another modal.
    shopInputPointer=null;shopInputKey=null;
    const nonPointer=event.detail===0&&!event.pointerType;
    const keyboard=nonPointer&&key&&key.button===button&&key.epoch===shopInputEpoch;
    // Screen-reader activation does not necessarily dispatch pointer events.
    const accessible=nonPointer&&event.isTrusted;
    const pointer=input&&input.button===button&&input.epoch===shopInputEpoch&&input.released&&!input.cancelled&&performance.now()-input.releasedAt<1000&&(!event.pointerType||event.pointerId===input.id);
    if(!isOpen()||button.disabled||!(keyboard||accessible||pointer))stop(event);
  },true);
})();
/* END RINGU SHOP INPUT V2 */
"""
replace('<button id="auraShopQuick" data-open-aura-shop="1" onclick="openAuraShop()" onpointerup="openAuraShop()">상점</button>', '<button id="auraShopQuick" data-open-aura-shop="1" type="button">상점</button>')
replace("function openAuraShop(){const modal=$('auraShopModal');if(!modal)return toast('상점을 불러오지 못했습니다.');modal.classList.add('show');renderAuraShop()}", input_code+"\nfunction openAuraShop(){const modal=$('auraShopModal');if(!modal)return toast('상점을 불러오지 못했습니다.');if(modal.classList.contains('show'))return;resetShopInput();renderAuraShop();modal.classList.add('show')}")
replace("function closeAuraShop(){cancelShopPurchase();$('auraShopModal').classList.remove('show')}", "function closeAuraShop(){cancelShopPurchase();resetShopInput();$('auraShopModal').classList.remove('show')}")
replace("document.addEventListener('click',e=>{const aura=e.target.closest('[data-open-aura-shop]');if(aura){e.preventDefault();return openAuraShop()}});", "// Open only on click, after release; consume it before rendering new controls.\ndocument.addEventListener('click',e=>{const aura=e.target.closest('[data-open-aura-shop]');if(aura){e.preventDefault();e.stopImmediatePropagation();return openAuraShop()}},true);")
replace("const aura=e.target.closest('[data-open-aura-shop]');if(aura){e.preventDefault();return openAuraShop()}const rank=", "const rank=")
result = text.encode('utf-8')
assert blob(result) == 'ffd307400845fa2367754c6d2f6bf949aac67632', 'Output differs from browser-tested source'

class Scripts(HTMLParser):
    def __init__(self):
        super().__init__(); self.active=False; self.parts=[]; self.scripts=[]
    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            attrs=dict(attrs)
            self.active=not attrs.get('src') and attrs.get('type','').lower() in ('','text/javascript','application/javascript','module')
            self.parts=[]
    def handle_data(self, data):
        if self.active:self.parts.append(data)
    def handle_endtag(self, tag):
        if tag=='script' and self.active:
            self.scripts.append(''.join(self.parts));self.active=False
parser=Scripts();parser.feed(text)
assert len(parser.scripts)==22
with tempfile.TemporaryDirectory() as tmp:
    for i,code in enumerate(parser.scripts):
        js=Path(tmp)/f'script-{i}.js';js.write_text(code,encoding='utf-8')
        subprocess.run(['node','--check',str(js)],check=True)
path.write_bytes(result)
print('PASS: exact tested HTML; 22 executable script syntax checks; output',blob(result))
