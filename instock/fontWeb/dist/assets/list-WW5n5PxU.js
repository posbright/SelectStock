import{d as fe,m as me,c as C,p as F,b as z,q as pe,h as k,g as m,a as o,w as a,r as u,t as w,n as N,s as _e,o as c,e as d,y as D,C as ye,D as ve,F as ge,f as be,G as ke,H as we,I as xe,J as he,E as r,v as Ce,B as G,A as Se,_ as Te}from"./index-DhvwI69_.js";import{c as Re,r as O,d as Y,e as j,f as Fe,h as De,m as Ae,i as Be,j as ze}from"./stock-53WNX4x-.js";const Ee={class:"algo-list"},Ke={key:0,class:"breadcrumb"},Ve={class:"folder-path"},Ne={class:"toolbar"},Ie={class:"name-cell"},Me={key:3,class:"name-text"},$e={key:0},Pe={key:0},Le={style:{display:"flex",gap:"12px"}},Ge=fe({__name:"list",setup(Oe){const q=Ce(),v=m([]),S=m([]),A=m(!1),p=m([]),g=m(0),E=m(""),T=m(null),B=m(""),R=m(!1),K=m(null),H={stock:"Code",multi_factor:"Factor",portfolio:"Portfolio",blank:"Code"},I={stock:`# 股票策略
def initialize(context):
    context.security = '000001'

def handle_data(context, data):
    security = context.security
    price = data[security].close
    ma5 = history(security, 5, 'close')
    if len(ma5) < 5:
        return
    ma_val = ma5.mean()
    if price > ma_val * 1.01 and security not in context.portfolio.positions:
        order_value(security, context.portfolio.available_cash * 0.9)
    elif price < ma_val * 0.99 and security in context.portfolio.positions:
        order_target(security, 0)
`,multi_factor:`# 多因子策略
def initialize(context):
    context.stocks = ['600519', '000858', '601318', '600036', '300750']
    context.rebalance_days = 0

def handle_data(context, data):
    context.rebalance_days += 1
    if context.rebalance_days % 20 != 1:
        return
    target = context.portfolio.total_value / len(context.stocks)
    for code in context.stocks:
        order_target_value(code, target)
`,portfolio:`# 组合策略
def initialize(context):
    context.stocks = ['000001', '600519', '601318']

def handle_data(context, data):
    momentum = {}
    for code in context.stocks:
        h = history(code, 20, 'close')
        if len(h) >= 20 and h.iloc[0] > 0:
            momentum[code] = h.iloc[-1] / h.iloc[0] - 1
    if not momentum:
        return
    best = max(momentum, key=momentum.get)
    for code in list(context.portfolio.positions.keys()):
        if code != best:
            order_target(code, 0)
    if best not in context.portfolio.positions:
        order_value(best, context.portfolio.available_cash * 0.9)
`,blank:`def initialize(context):
    pass

def handle_data(context, data):
    pass
`},x=N(()=>p.value.filter(t=>t.type==="strategy").map(t=>t.id)),J=N(()=>p.value.filter(t=>t.type==="folder").map(t=>t.id)),M=N(()=>{const t=[];if(g.value===0){for(const e of S.value)t.push({...e,rowKey:`folder-${e.id}`});for(const e of v.value.filter(n=>!n.folder_id||n.folder_id===0))t.push({...e,rowKey:`strategy-${e.id}`})}else for(const e of v.value.filter(n=>n.folder_id===g.value))t.push({...e,rowKey:`strategy-${e.id}`});return t});function U(t){return H[t]||"Code"}function Q(t){p.value=t}let b=null;function W(t,e,n){(e==null?void 0:e.type)!=="selection"&&(T.value||(b&&clearTimeout(b),b=setTimeout(()=>{b=null,Z(t)},200)))}function X(t,e,n){(e==null?void 0:e.type)!=="selection"&&(b&&(clearTimeout(b),b=null),ee(t))}function Z(t){if(!T.value){if(t.type==="folder"){g.value=t.id,E.value=t.name,console.log("[list] Enter folder:",t.id,t.name);return}q.push("/algo/edit/"+t.id)}}async function ee(t){T.value=t.rowKey,B.value=t.name,await Se()}function te(){g.value=0,E.value=""}async function $(t){const e=B.value.trim();if(T.value=null,!(!e||e===t.name))try{t.type==="folder"?await O(t.id,e):await Y(t.id,e),r.success("已重命名"),_()}catch{r.error("重命名失败")}}async function _(){A.value=!0;try{const t=await Re(),e=(t==null?void 0:t.data)||t;e!=null&&e.strategies?(v.value=e.strategies,S.value=e.folders||[]):Array.isArray(e)&&(v.value=e,S.value=[]),console.log("[list] loadData:",v.value.length,"strategies,",S.value.length,"folders, currentFolder=",g.value,"root strategies:",v.value.filter(n=>!n.folder_id||n.folder_id===0).length)}finally{A.value=!1}}async function P(t){var l;const n="一个简单的策略-"+(v.value.length+1);try{const i=await j({name:n,code:I[t]||I.blank,category:t,folder_id:g.value});((i==null?void 0:i.code)??((l=i==null?void 0:i.data)==null?void 0:l.code))===0?(r.success("策略已创建"),await _()):r.error((i==null?void 0:i.msg)||"创建失败")}catch{r.error("创建失败")}}async function L(){var t;if(!R.value){R.value=!0;try{await _();const e=await Fe(),n=Array.isArray(e==null?void 0:e.data)?e.data:Array.isArray(e)?e:[];if(!n.length){r.warning("无可用模板");return}const l=new Set(v.value.map(f=>f.name));let i=0;for(const f of n){if(l.has(f.name))continue;const y=await j({name:f.name,code:f.code,category:f.category||"stock"});((y==null?void 0:y.code)??((t=y==null?void 0:y.data)==null?void 0:t.code))===0&&(i++,l.add(f.name))}if(i===0){r.info("所有模板已导入");return}r.success("已导入 "+i+" 个示例策略"),await _()}catch{r.error("导入失败")}finally{R.value=!1}}}async function ae(){const{value:t}=await G.prompt("请输入文件夹名称","新建文件夹",{confirmButtonText:"创建",inputValue:"新文件夹",inputPattern:/\S+/}).catch(()=>({value:""}));if(t)try{await De(t),r.success("文件夹已创建"),_()}catch{r.error("创建失败")}}async function oe(){if(p.value.length!==1){r.warning("请选择一个项目");return}const t=p.value[0],{value:e}=await G.prompt("新名称","重命名",{confirmButtonText:"确定",inputValue:t.name,inputPattern:/\S+/}).catch(()=>({value:""}));if(e)try{t.type==="folder"?await O(t.id,e):await Y(t.id,e),r.success("已重命名"),_()}catch{r.error("重命名失败")}}async function le(t){var e,n;if(x.value.length!==0)try{const l=await Ae(x.value,t);if(((l==null?void 0:l.code)??((e=l==null?void 0:l.data)==null?void 0:e.code))!==0){r.error((l==null?void 0:l.msg)||((n=l==null?void 0:l.data)==null?void 0:n.msg)||"移动失败");return}r.success("已移动"),p.value=[],K.value&&K.value.clearSelection(),await _()}catch(l){console.error("moveStrategy error:",l),r.error("移动失败")}}async function ne(){try{x.value.length>0&&await Be(x.value);for(const t of J.value)await ze(t);r.success("已删除"),_()}catch{r.error("删除失败")}}return me(_),(t,e)=>{const n=u("el-icon"),l=u("el-button"),i=u("el-dropdown-item"),f=u("el-dropdown-menu"),y=u("el-dropdown"),ie=u("el-popconfirm"),h=u("el-table-column"),se=u("el-input"),re=u("el-tag"),de=u("el-table"),ce=u("el-empty"),ue=_e("loading");return c(),C("div",Ee,[g.value>0?(c(),C("div",Ke,[o(l,{text:"",size:"small",onClick:te},{default:a(()=>[o(n,null,{default:a(()=>[o(D(ye))]),_:1}),e[2]||(e[2]=d(" 返回根目录 ",-1))]),_:1}),z("span",Ve,"/ "+w(E.value),1)])):F("",!0),z("div",Ne,[o(y,{onCommand:P,trigger:"click"},{dropdown:a(()=>[o(f,null,{default:a(()=>[o(i,{command:"stock"},{default:a(()=>[...e[4]||(e[4]=[d("股票策略",-1)])]),_:1}),o(i,{command:"multi_factor"},{default:a(()=>[...e[5]||(e[5]=[d("多因子策略",-1)])]),_:1}),o(i,{command:"portfolio"},{default:a(()=>[...e[6]||(e[6]=[d("组合策略",-1)])]),_:1}),o(i,{command:"blank"},{default:a(()=>[...e[7]||(e[7]=[d("空白模版",-1)])]),_:1})]),_:1})]),default:a(()=>[o(l,{type:"primary"},{default:a(()=>[...e[3]||(e[3]=[d("+ 新建策略",-1)])]),_:1})]),_:1}),o(l,{onClick:ae},{default:a(()=>[o(n,null,{default:a(()=>[o(D(ve))]),_:1}),e[8]||(e[8]=d(" 新建文件夹",-1))]),_:1}),o(l,{disabled:p.value.length===0,onClick:oe},{default:a(()=>[...e[9]||(e[9]=[d("重命名",-1)])]),_:1},8,["disabled"]),o(y,{disabled:x.value.length===0,onCommand:le,trigger:"click"},{dropdown:a(()=>[o(f,null,{default:a(()=>[o(i,{command:0},{default:a(()=>[...e[11]||(e[11]=[d("根目录",-1)])]),_:1}),(c(!0),C(ge,null,be(S.value,s=>(c(),k(i,{key:s.id,command:s.id},{default:a(()=>[d(w(s.name),1)]),_:2},1032,["command"]))),128))]),_:1})]),default:a(()=>[o(l,{disabled:x.value.length===0},{default:a(()=>[...e[10]||(e[10]=[d("移动到",-1)])]),_:1},8,["disabled"])]),_:1},8,["disabled"]),o(ie,{title:"确定删除选中的项目？",onConfirm:ne,disabled:p.value.length===0},{reference:a(()=>[o(l,{disabled:p.value.length===0,type:"danger",plain:""},{default:a(()=>[o(n,null,{default:a(()=>[o(D(ke))]),_:1}),e[12]||(e[12]=d(" 删除 ",-1))]),_:1},8,["disabled"])]),_:1},8,["disabled"]),o(l,{onClick:L,loading:R.value,style:{"margin-left":"auto"}},{default:a(()=>[...e[13]||(e[13]=[d("导入示例策略",-1)])]),_:1},8,["loading"])]),pe((c(),k(de,{ref_key:"tableRef",ref:K,data:M.value,onSelectionChange:Q,onRowClick:W,onRowDblclick:X,stripe:"","row-key":"rowKey",style:{width:"100%"}},{default:a(()=>[o(h,{type:"selection",width:"40"}),o(h,{label:"","min-width":"280"},{default:a(({row:s})=>[z("div",Ie,[s.type==="folder"?(c(),k(n,{key:0,size:18,color:"#e6a23c"},{default:a(()=>[o(D(we))]),_:1})):(c(),k(n,{key:1,size:18,color:"#409eff"},{default:a(()=>[o(D(xe))]),_:1})),T.value===s.rowKey?(c(),k(se,{key:2,modelValue:B.value,"onUpdate:modelValue":e[0]||(e[0]=V=>B.value=V),size:"small",style:{width:"220px"},onBlur:V=>$(s),onKeyup:he(V=>$(s),["enter"]),ref:"renameInput"},null,8,["modelValue","onBlur","onKeyup"])):(c(),C("span",Me,w(s.name),1))])]),_:1}),o(h,{label:"分类",width:"100",align:"center"},{default:a(({row:s})=>[s.type==="strategy"?(c(),k(re,{key:0,size:"small",type:"info",effect:"plain"},{default:a(()=>[d(w(U(s.category)),1)]),_:2},1024)):F("",!0)]),_:1}),o(h,{label:"最后修改时间",width:"180",align:"center"},{default:a(({row:s})=>[d(w(s.updated_at||s.created_at||""),1)]),_:1}),o(h,{label:"历史编译运行",width:"120",align:"center"},{default:a(({row:s})=>[s.type==="strategy"?(c(),C("span",$e,w(s.compile_count||0),1)):F("",!0)]),_:1}),o(h,{label:"历史回测",width:"100",align:"center"},{default:a(({row:s})=>[s.type==="strategy"?(c(),C("span",Pe,w(s.backtest_count||0),1)):F("",!0)]),_:1})]),_:1},8,["data"])),[[ue,A.value]]),!A.value&&M.value.length===0?(c(),k(ce,{key:1,description:"还没有策略，点击「新建策略」或导入示例策略"},{default:a(()=>[z("div",Le,[o(l,{type:"primary",onClick:e[1]||(e[1]=s=>P("stock"))},{default:a(()=>[...e[14]||(e[14]=[d("新建股票策略",-1)])]),_:1}),o(l,{onClick:L,loading:R.value},{default:a(()=>[...e[15]||(e[15]=[d("导入示例策略",-1)])]),_:1},8,["loading"])])]),_:1})):F("",!0)])}}}),qe=Te(Ge,[["__scopeId","data-v-34993ed1"]]);export{qe as default};
