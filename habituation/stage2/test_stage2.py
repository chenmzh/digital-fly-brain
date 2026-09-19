import json
from pathlib import Path
import unittest
import numpy as np
from surrogates import expected_sensory,pulse_state,silence,episode_features,predict

SPEC=json.loads((Path(__file__).parent/'cycle2_spec.json').read_text())


class StateTests(unittest.TestCase):
    def test_input_reset_collision(self):
        pattern=(np.array([0,0,0,1,1]),np.array([0,1,2,3,5]))
        np.testing.assert_array_equal(expected_sensory(pattern,2),np.array([[1,0],[3,0],[4,1],[6,1]]))

    def test_zero_depletion(self):
        feature,end=pulse_state(1.,150,.2,2.,0.,'resource')
        self.assertAlmostEqual(end,1.);np.testing.assert_allclose(feature,[1.,-1.])

    def test_exact_silence(self):
        self.assertAlmostEqual(silence(.2,2.,2.,'resource'),1-.8/np.e)
        self.assertAlmostEqual(silence(.8,2.,2.,'accumulator'),.8/np.e)

    def test_finite_pulse_resource_bounds(self):
        for f in [0,100,150,200]:
            feature,end=pulse_state(.5,f,.4,2.,.01,'resource')
            self.assertTrue(0<=end<=1)
            self.assertTrue(0<=feature[0]<=max(1,f/150))

    def test_independent_recovery_branches(self):
        c=SPEC['control'];a=episode_features('resource',c,150,SPEC)
        b=episode_features('resource',c,150,{**SPEC,'recovery_ms':[5000.,1000.]})
        for rest in [1000.,5000.]:
            x=next(r for r in a if r['phase']=='recovery' and r['rest_ms']==rest)
            y=next(r for r in b if r['phase']=='recovery' and r['rest_ms']==rest)
            np.testing.assert_array_equal(x['features'],y['features'])
        self.assertEqual(len(a),14)

    def test_nonnegative_output(self):
        np.testing.assert_array_equal(predict([[.2,-1],[1,-1]],[1,2],[10,5]),[0,10])


if __name__=='__main__':unittest.main()
