import{d as ue,m as fe,c as h,p as T,b as A,q as me,h as b,g as p,a as o,w as a,r as u,t as k,n as K,s as pe,o as c,e as d,y as R,C as _e,D as ye,F as ve,f as ge,G as be,H as ke,I as xe,J as we,E as r,v as he,B as P,A as Ce,_ as Se}from"./index-CqPZJwC8.js";import{c as Te,r as L,d as G,e as O,f as Re,h as Fe,m as De,i as Ae,j as Be}from"./stock-DvmStG6x.js";const ze={class:"algo-list"},Ee={key:0,class:"breadcrumb"},Ke={class:"folder-path"},Ve={class:"toolbar"},Ie={class:"name-cell"},Ne={key:3,class:"name-text"},Me={key:0},$e={key:0},Pe={style:{display:"flex",gap:"12px"}},Le=ue({__name:"list",setup(Ge){const Y=he(),y=p([]),C=p([]),F=p(!1),f=p([]),v=p(0),B=p(""),S=p(null),D=p(""),z=p(null),j={stock:"Code",multi_factor:"Factor",portfolio:"Portfolio",blank:"Code"},V={stock:`# 股票策略
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
`},x=K(()=>f.value.filter(t=>t.type==="strategy").map(t=>t.id)),q=K(()=>f.value.filter(t=>t.type==="folder").map(t=>t.id)),I=K(()=>{const t=[];if(v.value===0){for(const e of C.value)t.push({...e,rowKey:`folder-${e.id}`});for(const e of y.value.filter(n=>!n.folder_id||n.folder_id===0))t.push({...e,rowKey:`strategy-${e.id}`})}else for(const e of y.value.filter(n=>n.folder_id===v.value))t.push({...e,rowKey:`strategy-${e.id}`});return t});function H(t){return j[t]||"Code"}function J(t){f.value=t}let g=null;function U(t,e,n){(e==null?void 0:e.type)!=="selection"&&(S.value||(g&&clearTimeout(g),g=setTimeout(()=>{g=null,W(t)},200)))}function Q(t,e,n){(e==null?void 0:e.type)!=="selection"&&(g&&(clearTimeout(g),g=null),X(t))}function W(t){if(!S.value){if(t.type==="folder"){v.value=t.id,B.value=t.name,console.log("[list] Enter folder:",t.id,t.name);return}Y.push("/algo/edit/"+t.id)}}async function X(t){S.value=t.rowKey,D.value=t.name,await Ce()}function Z(){v.value=0,B.value=""}async function N(t){const e=D.value.trim();if(S.value=null,!(!e||e===t.name))try{t.type==="folder"?await L(t.id,e):await G(t.id,e),r.success("已重命名"),_()}catch{r.error("重命名失败")}}async function _(){F.value=!0;try{const t=await Te(),e=(t==null?void 0:t.data)||t;e!=null&&e.strategies?(y.value=e.strategies,C.value=e.folders||[]):Array.isArray(e)&&(y.value=e,C.value=[]),console.log("[list] loadData:",y.value.length,"strategies,",C.value.length,"folders, currentFolder=",v.value,"root strategies:",y.value.filter(n=>!n.folder_id||n.folder_id===0).length)}finally{F.value=!1}}async function M(t){var l;const n="一个简单的策略-"+(y.value.length+1);try{const i=await O({name:n,code:V[t]||V.blank,category:t,folder_id:v.value});((i==null?void 0:i.code)??((l=i==null?void 0:i.data)==null?void 0:l.code))===0?(r.success("策略已创建"),await _()):r.error((i==null?void 0:i.msg)||"创建失败")}catch{r.error("创建失败")}}async function ee(){var t;try{const e=await Re(),n=Array.isArray(e==null?void 0:e.data)?e.data:Array.isArray(e)?e:[];if(!n.length){r.warning("无可用模板");return}let l=0;for(const i of n){const m=await O({name:i.name,code:i.code,category:i.category||"stock"});((m==null?void 0:m.code)??((t=m==null?void 0:m.data)==null?void 0:t.code))===0&&l++}r.success("已导入 "+l+" 个示例策略"),await _()}catch{r.error("导入失败")}}async function te(){const{value:t}=await P.prompt("请输入文件夹名称","新建文件夹",{confirmButtonText:"创建",inputValue:"新文件夹",inputPattern:/\S+/}).catch(()=>({value:""}));if(t)try{await Fe(t),r.success("文件夹已创建"),_()}catch{r.error("创建失败")}}async function ae(){if(f.value.length!==1){r.warning("请选择一个项目");return}const t=f.value[0],{value:e}=await P.prompt("新名称","重命名",{confirmButtonText:"确定",inputValue:t.name,inputPattern:/\S+/}).catch(()=>({value:""}));if(e)try{t.type==="folder"?await L(t.id,e):await G(t.id,e),r.success("已重命名"),_()}catch{r.error("重命名失败")}}async function oe(t){var e,n;if(x.value.length!==0)try{const l=await De(x.value,t);if(((l==null?void 0:l.code)??((e=l==null?void 0:l.data)==null?void 0:e.code))!==0){r.error((l==null?void 0:l.msg)||((n=l==null?void 0:l.data)==null?void 0:n.msg)||"移动失败");return}r.success("已移动"),f.value=[],z.value&&z.value.clearSelection(),await _()}catch(l){console.error("moveStrategy error:",l),r.error("移动失败")}}async function le(){try{x.value.length>0&&await Ae(x.value);for(const t of q.value)await Be(t);r.success("已删除"),_()}catch{r.error("删除失败")}}return fe(_),(t,e)=>{const n=u("el-icon"),l=u("el-button"),i=u("el-dropdown-item"),m=u("el-dropdown-menu"),$=u("el-dropdown"),ne=u("el-popconfirm"),w=u("el-table-column"),ie=u("el-input"),se=u("el-tag"),re=u("el-table"),de=u("el-empty"),ce=pe("loading");return c(),h("div",ze,[v.value>0?(c(),h("div",Ee,[o(l,{text:"",size:"small",onClick:Z},{default:a(()=>[o(n,null,{default:a(()=>[o(R(_e))]),_:1}),e[2]||(e[2]=d(" 返回根目录 ",-1))]),_:1}),A("span",Ke,"/ "+k(B.value),1)])):T("",!0),A("div",Ve,[o($,{onCommand:M,trigger:"click"},{dropdown:a(()=>[o(m,null,{default:a(()=>[o(i,{command:"stock"},{default:a(()=>[...e[4]||(e[4]=[d("股票策略",-1)])]),_:1}),o(i,{command:"multi_factor"},{default:a(()=>[...e[5]||(e[5]=[d("多因子策略",-1)])]),_:1}),o(i,{command:"portfolio"},{default:a(()=>[...e[6]||(e[6]=[d("组合策略",-1)])]),_:1}),o(i,{command:"blank"},{default:a(()=>[...e[7]||(e[7]=[d("空白模版",-1)])]),_:1})]),_:1})]),default:a(()=>[o(l,{type:"primary"},{default:a(()=>[...e[3]||(e[3]=[d("+ 新建策略",-1)])]),_:1})]),_:1}),o(l,{onClick:te},{default:a(()=>[o(n,null,{default:a(()=>[o(R(ye))]),_:1}),e[8]||(e[8]=d(" 新建文件夹",-1))]),_:1}),o(l,{disabled:f.value.length===0,onClick:ae},{default:a(()=>[...e[9]||(e[9]=[d("重命名",-1)])]),_:1},8,["disabled"]),o($,{disabled:x.value.length===0,onCommand:oe,trigger:"click"},{dropdown:a(()=>[o(m,null,{default:a(()=>[o(i,{command:0},{default:a(()=>[...e[11]||(e[11]=[d("根目录",-1)])]),_:1}),(c(!0),h(ve,null,ge(C.value,s=>(c(),b(i,{key:s.id,command:s.id},{default:a(()=>[d(k(s.name),1)]),_:2},1032,["command"]))),128))]),_:1})]),default:a(()=>[o(l,{disabled:x.value.length===0},{default:a(()=>[...e[10]||(e[10]=[d("移动到",-1)])]),_:1},8,["disabled"])]),_:1},8,["disabled"]),o(ne,{title:"确定删除选中的项目？",onConfirm:le,disabled:f.value.length===0},{reference:a(()=>[o(l,{disabled:f.value.length===0,type:"danger",plain:""},{default:a(()=>[o(n,null,{default:a(()=>[o(R(be))]),_:1}),e[12]||(e[12]=d(" 删除 ",-1))]),_:1},8,["disabled"])]),_:1},8,["disabled"])]),me((c(),b(re,{ref_key:"tableRef",ref:z,data:I.value,onSelectionChange:J,onRowClick:U,onRowDblclick:Q,stripe:"","row-key":"rowKey",style:{width:"100%"}},{default:a(()=>[o(w,{type:"selection",width:"40"}),o(w,{label:"","min-width":"280"},{default:a(({row:s})=>[A("div",Ie,[s.type==="folder"?(c(),b(n,{key:0,size:18,color:"#e6a23c"},{default:a(()=>[o(R(ke))]),_:1})):(c(),b(n,{key:1,size:18,color:"#409eff"},{default:a(()=>[o(R(xe))]),_:1})),S.value===s.rowKey?(c(),b(ie,{key:2,modelValue:D.value,"onUpdate:modelValue":e[0]||(e[0]=E=>D.value=E),size:"small",style:{width:"220px"},onBlur:E=>N(s),onKeyup:we(E=>N(s),["enter"]),ref:"renameInput"},null,8,["modelValue","onBlur","onKeyup"])):(c(),h("span",Ne,k(s.name),1))])]),_:1}),o(w,{label:"分类",width:"100",align:"center"},{default:a(({row:s})=>[s.type==="strategy"?(c(),b(se,{key:0,size:"small",type:"info",effect:"plain"},{default:a(()=>[d(k(H(s.category)),1)]),_:2},1024)):T("",!0)]),_:1}),o(w,{label:"最后修改时间",width:"180",align:"center"},{default:a(({row:s})=>[d(k(s.updated_at||s.created_at||""),1)]),_:1}),o(w,{label:"历史编译运行",width:"120",align:"center"},{default:a(({row:s})=>[s.type==="strategy"?(c(),h("span",Me,k(s.compile_count||0),1)):T("",!0)]),_:1}),o(w,{label:"历史回测",width:"100",align:"center"},{default:a(({row:s})=>[s.type==="strategy"?(c(),h("span",$e,k(s.backtest_count||0),1)):T("",!0)]),_:1})]),_:1},8,["data"])),[[ce,F.value]]),!F.value&&I.value.length===0?(c(),b(de,{key:1,description:"还没有策略，点击「新建策略」或导入示例策略"},{default:a(()=>[A("div",Pe,[o(l,{type:"primary",onClick:e[1]||(e[1]=s=>M("stock"))},{default:a(()=>[...e[13]||(e[13]=[d("新建股票策略",-1)])]),_:1}),o(l,{onClick:ee},{default:a(()=>[...e[14]||(e[14]=[d("导入示例策略",-1)])]),_:1})])]),_:1})):T("",!0)])}}}),je=Se(Le,[["__scopeId","data-v-2615cf0b"]]);export{je as default};
