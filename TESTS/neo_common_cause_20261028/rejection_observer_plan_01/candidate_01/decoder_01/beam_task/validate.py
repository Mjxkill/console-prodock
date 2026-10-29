import unittest,sys,json
import test_adversarial
suite=unittest.defaultTestLoader.loadTestsFromModule(test_adversarial)
result=unittest.TextTestRunner(verbosity=2).run(suite)
if result.testsRun<24:raise AssertionError('At least24 independently named cases required')
print(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'passed':result.wasSuccessful(),'hardware':False}))
sys.exit(0 if result.wasSuccessful() else 1)
