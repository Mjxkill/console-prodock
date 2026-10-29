import json
from truth import evaluate
g=json.load(open('graph.json'))
count=0
for state in range(32):
 for old_bad in (0,1):
  for start in (0,1):
   for reset_released in (0,1):
    for bad in range(8):
     inputs={f'state_0[{i}]':(state>>i)&1 for i in range(5)}
     inputs.update({f'descriptor_bad[{i}]':(bad>>i)&1 for i in range(3)})
     inputs.update({'copy_bad':old_bad,'state[41]':start,'gpu_debug_state[50]':reset_released})
     expected=1 if state>=19 or (state==17 and bad) else 0 if state==0 and start else old_bad
     assert evaluate(g,'n4731_54',inputs)==expected,(state,old_bad,start,bad)
     assert evaluate(g,'n5984_12',inputs)==int(state==1 and reset_released)
     assert evaluate(g,'n7630_6',inputs)==int(state==0 and start and reset_released)
     count+=1
# Invalid data must never become an invented Boolean answer.
for graph,out,inputs in [(g,'absent',{}),({'cells':{'x':{'kind':'LUT1','ports':{'F':'a','I0':'a'},'parameters':{'INIT':"2'h2"}}}},'a',{}),({'cells':{'x':{'kind':'ALU','ports':{'F':'a'},'parameters':{}}}},'a',{})]:
 try:evaluate(graph,out,inputs)
 except (ValueError,KeyError):pass
 else:raise AssertionError('invalid graph accepted')
print(json.dumps({'passed':True,'combinations':count,'primitive_cones':3,'descriptor_reject_state':17,'default_bad_states':list(range(19,32)),'IDLE':0,'CHECK':1,'clocked_or_hardware_proof':False}))
