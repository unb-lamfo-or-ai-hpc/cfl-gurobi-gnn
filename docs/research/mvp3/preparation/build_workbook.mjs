import fs from "node:fs/promises";
import path from "node:path";
import {fileURLToPath} from "node:url";
import {Workbook, SpreadsheetFile} from "@oai/artifact-tool";

const here=path.dirname(fileURLToPath(import.meta.url));
const output=path.resolve(process.argv[2]||here);
const qa=path.resolve(process.argv[3]||path.join(output,"qa"));
await fs.mkdir(output,{recursive:true});await fs.mkdir(qa,{recursive:true});
const d=JSON.parse(await fs.readFile(path.join(here,"planning-registers.json"),"utf8"));
const wb=Workbook.create();
const names=["Sprints","Budget","Research design","Acceptance","Instances","Evaluation","Appendices"];
const sheets=Object.fromEntries(names.map(n=>[n,wb.worksheets.add(n)]));
const navy="#20374D", amber="#FFF2CC", grey="#EEF2F5";
function block(s,range,values){s.getRange(range).values=values;}
function base(s,range,title,widths){
 s.showGridLines=false;s.getRange(range).format.font={name:"Arial",size:10,color:"#202B35"};
 s.getRange(range).format.verticalAlignment="center";
 s.getRange("A2").values=[[title]];s.getRange("A2").format.font={name:"Arial",size:14,bold:true};
 for(let i=0;i<widths.length;i++)s.getRange(String.fromCharCode(65+i)+"1:"+String.fromCharCode(65+i)+range.match(/\d+$/)[0]).format.columnWidthPx=widths[i];
}
function head(s,range){s.getRange(range).format={fill:navy,font:{name:"Arial",size:10,bold:true,color:"#FFFFFF"},wrapText:true,rowHeight:35,horizontalAlignment:"center",verticalAlignment:"center"};}
function rows(s,range,height=40){s.getRange(range).format.wrapText=true;s.getRange(range).format.rowHeight=height;}
function note(s,text){s.getRange("A3").values=[[text]];s.getRange("A3").format.font={name:"Arial",size:10,italic:true,color:"#596876"};}
const source="Source: approved protocol v3 (PR99); planning-registers.json. Planning values, not research results.";
let s=sheets.Sprints;base(s,"A1:D13","MVP 3.0 | development Sprints",[65,280,390,470]);note(s,"Approved v3 baseline; implementation begins in the next chat. Concrete releases remain author decisions.");
head(s,"A5:D5");block(s,"A5:D5",[["Sprint","Work and window","Planned PR packages","Accepted output"]]);
block(s,"A6:D11",d.sprints.map(x=>[x.id,x.title+"\n"+x.window,x.packages,x.deliverable]));rows(s,"A6:D11",52);s.tabColor=navy;

s=sheets.Budget;base(s,"A1:E63","MVP 3.0 | resource budget",[350,130,170,175,145]);note(s,source);
block(s,"A5:D5",[["Planning driver","Value","Unit","Definition"]]);head(s,"A5:D5");
const inputs=[
["Root calls",66,"calls","66 parents"],["Label calls",66,"calls","independent incumbent runs"],["Evaluation calls",45,"calls","15 parents x B/R/G"],
["Optimisation allowance",8,"hours/call","28800 seconds"],["Job envelope",12,"hours/call","reservation ceiling"],["Concurrent slots",2,"jobs","maximum two"],
["Physical cores per node",32,"cores","selected Intel class"],["Logical CPUs per node",64,"Slurm CPUs","one task"],["Easy/medium RAM",192,"GiB","exclusive Intel allocation"],
["Hard RAM",384,"GiB","exclusive Intel allocation"],["Serial GPUs",1,"V100 devices","one arm"],["DDP GPUs",4,"V100 devices","matched global work"],
["Training walltime per arm",6,"hours","two arms"],["CPU artifact allowance",24,"job-hours","12 graph + 8 Start + 4 reconcile"],["Conditional hard calls",6,"calls","separate release only"],
["Training parents",42,"parents","training partition"],["Epochs",100,"epochs","per arm"],["Draws per parent/epoch",4,"draws","per arm"],["Global batch",4,"graphs","serial and DDP"],
["Easy calls in scenario",72,"calls","preparation plus evaluation"],["Other calls in scenario",105,"calls","medium and hard"],["Easy scenario time",1,"hours/call","historically informed"],
["Other scenario time",8,"hours/call","allowance anchor"],["Scenario overhead",0.25,"hours/call","loading/export allowance"],["Devices per GPU node",8,"device slots","whole-node accounting"],
["Hard parents",6,"parents","two preparation + three evaluation calls each"]];
block(s,"A6:D31",inputs);rows(s,"A6:D31",29);s.getRange("B6:B31").format.fill=amber;s.getRange("B6:B31").format.numberFormat="#,##0";s.getRange("B29").format.numberFormat="0.00";
s.getRange("B11").dataValidation={rule:{type:"list",values:["1","2"]}};
block(s,"A33:E33",[["Stage","Calls","Maximum solver-h","Reserved job-h","Two-slot waves"]]);head(s,"A33:E33");
for(const [row,label,driver] of [[34,"Root features",6],[35,"Incumbent labels",7],[36,"B/R/G evaluation",8],[39,"Conditional hard diagnostic",20]]){
 s.getRange("A"+row).values=[[label]];
 s.getRange("B"+row+":E"+row).formulas=[[
 '=IF(B'+driver+'="","n.a.",B'+driver+')',
 '=IF(OR(B'+row+'="n.a.",$B$9=""),"n.a.",B'+row+'*$B$9)',
 '=IF(OR(B'+row+'="n.a.",$B$10=""),"n.a.",B'+row+'*$B$10)',
 '=IF(OR(B'+row+'="n.a.",$B$11<=0),"n.a.",ROUNDUP(B'+row+'/$B$11,0))'
 ]];
}
s.getRange("A37").values=[["PRIMARY TOTAL"]];
for(const col of ["B","C","D","E"])s.getRange(col+"37").formulas=[['=IF(COUNT('+col+'34:'+col+'36)<>3,"n.a.",SUM('+col+'34:'+col+'36))']];
s.getRange("A37:E37").format.fill=grey;rows(s,"A34:E39",31);
block(s,"A42:C42",[["Derived planning quantity","Value","Unit"]]);head(s,"A42:C42");
const metrics=[
[43,"Full-reservation calendar",'=IF(OR(E37="n.a.",B10=""),"n.a.",E37*B10)',"hours"],
[44,"Full-reservation calendar",'=IF(B43="n.a.","n.a.",B43/24)',"days"],
[45,"Solver stage-wave calendar",'=IF(OR(E37="n.a.",B9=""),"n.a.",E37*B9)',"hours"],
[46,"Solver stage-wave calendar",'=IF(B45="n.a.","n.a.",B45/24)',"days"],
[47,"Working scenario optimisation",'=IF(COUNT(B25:B28)<>4,"n.a.",B25*B27+B26*B28)',"hours"],
[48,"Working scenario jobs",'=IF(OR(B47="n.a.",B37="n.a.",B29=""),"n.a.",B47+B37*B29)',"job-hours"],
[49,"Working scenario calendar lower bound",'=IF(OR(B48="n.a.",B11<=0),"n.a.",B48/B11/24)',"days"],
[50,"Primary physical-core reservation",'=IF(OR(D37="n.a.",B12=""),"n.a.",D37*B12)',"core-hours"],
[51,"Primary logical CPU reservation",'=IF(OR(D37="n.a.",B13=""),"n.a.",D37*B13)',"Slurm CPU-hours"],
[52,"Primary memory reservation",'=IF(OR(B37="n.a.",COUNT(B14:B15)<>2,B31="",B10=""),"n.a.",((B37-5*B31)*B14+5*B31*B15)*B10)',"GiB-hours"],
[53,"Model-requested GPU envelope",'=IF(COUNT(B16:B18)<>3,"n.a.",(B16+B17)*B18)',"GPU-hours"],
[54,"Exclusive GPU-node occupancy",'=IF(B18="","n.a.",2*B18)',"node-hours"],
[55,"Whole-node GPU device slots",'=IF(OR(B54="n.a.",B30=""),"n.a.",B54*B30)',"device-slot hours"],
[56,"Graph presentations per epoch",'=IF(OR(B21="",B23=""),"n.a.",B21*B23)',"draws"],
[57,"Global updates per epoch",'=IF(OR(B56="n.a.",B24<=0),"n.a.",B56/B24)',"updates"],
[58,"Global updates per arm",'=IF(OR(B57="n.a.",B22=""),"n.a.",B57*B22)',"updates"],
[59,"Graph presentations per arm",'=IF(OR(B56="n.a.",B22=""),"n.a.",B56*B22)',"draws"],
[60,"Primary + artifacts + GPU node occupancy",'=IF(OR(D37="n.a.",B19="",B54="n.a."),"n.a.",D37+B19+B54)',"job/node-hours"],
[61,"Conditional job addition",'=IF(D39="n.a.","n.a.",D39)',"job-hours"]];
for(const [row,label,formula,unit] of metrics){s.getRange("A"+row).values=[[label]];s.getRange("B"+row).formulas=[[formula]];s.getRange("C"+row).values=[[unit]];}
rows(s,"A43:C61",32);s.getRange("B34:E39").format.numberFormat="#,##0";s.getRange("B43:B61").format.numberFormat="#,##0.00";
s.freezePanes.freezeRows(5);

s=sheets["Research design"];base(s,"A1:D30","MVP 3.0 | hypotheses and experimental design",[150,465,450,450]);note(s,"Interpretive propositions from the approved research questions; no additional arm or significance test.");
block(s,"A5:D5",[["ID","Proposition","Measurement/reference","Scope"]]);head(s,"A5:D5");
block(s,"A6:D10",d.hypotheses.map(x=>[x.id,x.proposition,x.reference+"\n"+x.evidence,x.interpretation]));rows(s,"A6:D10",78);
block(s,"A13:C13",[["Component","Planned control","Interpretation"]]);head(s,"A13:C13");
block(s,"A14:C27",d.design);rows(s,"A14:C27",56);s.freezePanes.freezeRows(5);

s=sheets.Acceptance;base(s,"A1:F13","MVP 3.0 | acceptance record",[60,340,580,150,160,125]);note(s,"Review fields are empty: no scientific Sprint acceptance is inferred from methodology approval.");
block(s,"A5:F5",[["Sprint","Required artifact","Acceptance evidence","Review status","Evidence reference","Decision date"]]);head(s,"A5:F5");
block(s,"A6:F11",d.sprints.map(x=>[x.id,x.deliverable,x.acceptance,"NOT_REVIEWED",null,null]));rows(s,"A6:F11",80);
s.getRange("D6:F11").format.fill=amber;s.getRange("D6:D11").dataValidation={rule:{type:"list",values:["NOT_REVIEWED","IN_REVIEW","ACCEPTED","REVISION_REQUIRED"]}};
s.getRange("F6:F11").format.numberFormat="yyyy-mm-dd";

s=sheets.Instances;base(s,"A1:E72","MVP 3.0 | original-instance register",[85,330,110,190,125]);note(s,"E/M partition roles are frozen in S1. This register contains no solver or learning observations.");
block(s,"A5:E5",[["Alias","Original ID","Family","Learning role","Status"]]);head(s,"A5:E5");
block(s,"A6:E71",d.instances.map(x=>[x.alias,x.original_id,x.family,x.learning_role,x.status]));rows(s,"A6:E71",26);
s.freezePanes.freezeRows(5);s.freezePanes.freezeColumns(2);

s=sheets.Evaluation;base(s,"A1:I51","MVP 3.0 | planned paired evaluation slots",[130,90,290,75,70,115,130,115,250]);note(s,"Slot labels are not frozen test-parent IDs. Empty numeric fields mean no observation, not zero.");
block(s,"A5:I5",[["Parent slot","Family","Original ID","Method","Seed","Status","Target time (s)","Gap target","Eligibility reason"]]);head(s,"A5:I5");
block(s,"A6:I50",d.evaluation.map(x=>[x.slot,x.family,x.original_id||null,x.method,x.seed,x.status,x.target_time_seconds,x.gap_target,x.eligibility_reason]));rows(s,"A6:I50",28);
s.getRange("G6:H50").format.fill=amber;s.getRange("G6:G50").format.numberFormat="0.000";s.getRange("H6:H50").format.numberFormat="0.00%";
s.freezePanes.freezeRows(5);s.freezePanes.freezeColumns(1);

s=sheets.Appendices;base(s,"A1:D13","MVP 3.0 | scientific and workbook appendices",[85,300,340,540]);note(s,"The workbook supports the approved scientific Appendices A-D; it is not the research evidence store.");
block(s,"A5:D5",[["ID","Appendix","Source/location","Purpose"]]);head(s,"A5:D5");block(s,"A6:D11",d.appendices);rows(s,"A6:D11",80);

wb.recalculate();
const b=sheets.Budget;
const controls={calls:b.getRange("B37").values[0][0],solverHours:b.getRange("C37").values[0][0],jobHours:b.getRange("D37").values[0][0],waves:b.getRange("E37").values[0][0],calendarDays:b.getRange("B44").values[0][0],workingDays:b.getRange("B49").values[0][0],GPUHours:b.getRange("B53").values[0][0],updates:b.getRange("B58").values[0][0]};
if(controls.calls!==177||controls.solverHours!==1416||controls.jobHours!==2124||controls.waves!==89||controls.calendarDays!==44.5||controls.GPUHours!==30||controls.updates!==4200)throw Error("Budget control mismatch "+JSON.stringify(controls));
// Disposable input edits are restored before final recalc, export and rendering.
b.getRange("B11").values=[[1]];wb.recalculate();if(b.getRange("B44").values[0][0]!==88.5)throw Error("Slot sensitivity failed");
b.getRange("B11").values=[[2]];
b.getRange("B9").values=[[null]];wb.recalculate();if(b.getRange("C37").values[0][0]!=="n.a.")throw Error("Missing driver hidden");
b.getRange("B9").values=[[8]];
b.getRange("B29").values=[[0]];wb.recalculate();if(b.getRange("B48").values[0][0]!==912)throw Error("Zero overhead failed");
b.getRange("B29").values=[[0.25]];
wb.recalculate();
const errors=await wb.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!|#CALC!",options:{useRegex:true,maxResults:30},maxChars:2500});
await fs.writeFile(path.join(qa,"formula-error-scan.json"),errors.ndjson);
const inspection=await wb.inspect({kind:"region",sheetId:"Budget",range:"A33:E61",include:"values,formulas",maxChars:6500,tableMaxRows:30,tableMaxCols:5});
await fs.writeFile(path.join(qa,"budget-inspection.json"),inspection.ndjson);
const views=[["Sprints","A1:D12"],["Budget","A1:E39"],["Budget","A42:C61"],["Research design","A1:D11"],["Research design","A13:C27"],["Acceptance","A1:F12"],["Instances","A1:E25"],["Instances","A48:E71"],["Evaluation","A1:I22"],["Evaluation","A33:I50"],["Appendices","A1:D12"]];
for(let i=0;i<views.length;i++){const [sheetName,range]=views[i];const png=await wb.render({sheetName,range,scale:1.3,format:"png"});await fs.writeFile(path.join(qa,"view-"+String(i+1).padStart(2,"0")+".png"),new Uint8Array(await png.arrayBuffer()));}
const x=await SpreadsheetFile.exportXlsx(wb);await x.save(path.join(output,"mvp3-preparation-workbook-EN.xlsx"));
await fs.writeFile(path.join(qa,"workbook-validation.json"),JSON.stringify({controls,checks:["baseline arithmetic","one-slot sensitivity","missing optimisation allowance remains unavailable","zero overhead preserved"],sheets:names,renderedViews:views.length,scientificObservations:0},null,2));
console.log(JSON.stringify({controls,sheets:names,renderedViews:views.length,output:path.join(output,"mvp3-preparation-workbook-EN.xlsx")}));

