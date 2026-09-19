import json
from pathlib import Path
import unittest
from metrics import train_metrics,recovery_metrics,h3_screen,threshold_bracket,strictly_earlier,expected_schedule

SPEC=json.loads((Path(__file__).parent/'protocol.json').read_text())


class Tests(unittest.TestCase):
    def test_constant_is_not_decrement(self):
        r=train_metrics([8]*12);self.assertFalse(r['decrement']);self.assertTrue(r['plateau'])

    def test_identical_cycles_do_not_potentiate(self):
        r=train_metrics([8,6,3,2,1,1,0,0,0,0,0,0]);self.assertFalse(h3_screen([r,r,r])['supported'])

    def test_inadequate_recovery_is_not_potentiation(self):
        a=train_metrics([8,6,3,2,1,1,0,0,0,0,0,0]);b=train_metrics([4,1,1,0,0,0,0,0,0,0,0,0])
        self.assertFalse(h3_screen([a,b,b])['eligible'])

    def test_same_crossing_bin_is_not_faster(self):
        a=threshold_bracket([200,500,1000,2000],[0,.2,.4,.8],.5)
        b=threshold_bracket([200,500,1000,2000],[0,.3,.45,.9],.5)
        self.assertFalse(strictly_earlier(a,b));self.assertFalse(strictly_earlier(b,a))

    def test_adjacent_bins_ordered(self):
        a=threshold_bracket([200,500,1000,2000],[0,.3,.6,.9],.5)
        b=threshold_bracket([200,500,1000,2000],[0,.2,.4,.8],.5)
        self.assertTrue(strictly_earlier(a,b))

    def test_nonmonotonic_not_timing_proof(self):
        a=threshold_bracket([200,500,1000,2000],[.6,.1,.3,.8],.5)
        b=threshold_bracket([200,500,1000,2000],[0,.2,.4,.8],.5)
        self.assertFalse(strictly_earlier(a,b))

    def test_fraction_not_clipped(self):
        train={'initial':8,'late':4};r=recovery_metrics(train,[200,500,1000],[3,6,9])
        self.assertEqual(r['F'],[-.25,.5,1.25])

    def test_zero_loss_undefined(self):
        r=recovery_metrics({'initial':8,'late':8},[200,500],[8,8]);self.assertEqual(r['half_lost']['status'],'undefined')

    def test_unusable_main_readout_is_ineligible_not_crash(self):
        from analyze import main_scores,pd
        rows=[{**r,'seed':seed,'aBN1':0} for seed in SPEC['seeds'] for r in expected_schedule('main',SPEC) if r['kind']=='response']
        scores,_,_=main_scores(pd.DataFrame(rows),SPEC)
        self.assertTrue(all(not r['eligible'] for r in scores))
        self.assertTrue(all(not r['supported'] for r in scores))

    def test_schedule_main(self):
        rows=expected_schedule('main',SPEC);r=[x for x in rows if x['kind']=='response'];self.assertEqual(len(r),87)
        b2=next(x for x in r if x['case']=='h3' and x['block']==2 and x['pulse']==0)
        b3=next(x for x in r if x['case']=='h3' and x['block']==3 and x['pulse']==0)
        self.assertAlmostEqual(b2['onset_s'],15.8);self.assertAlmostEqual(b3['onset_s'],31.6)
        final=next(x for x in r if x['case']=='fast24' and x['pulse']==23);self.assertAlmostEqual(final['onset_s'],11.5)

    def test_schedule_frequency_supplement(self):
        spec={**SPEC,'slow_interval_ms':750.,'n_train':24,'recovery_ms':[500.,1000.,2000.,5000.]}
        rows=expected_schedule('frequency',spec);r=[x for x in rows if x['kind']=='response']
        self.assertEqual(len(rows),55);self.assertEqual(len(r),28)
        self.assertEqual(r[23]['onset_s'],17.25);self.assertEqual(r[24]['onset_s'],18.05)

    def test_qualified_but_unresolved_frequency_is_not_support(self):
        from analyze import frequency_scores,pd
        spec={**SPEC,'recovery_ms':[500.,1000.,2000.,5000.]};d=[];trains=[];profiles=[]
        for seed in SPEC['seeds']:
            for i,y in enumerate([8,6,4]+[2]*21):d.append({'seed':seed,'case':'frequency24','phase':'train','pulse':i,'rest_ms':0.,'aBN1':y})
            for t,y in zip(spec['recovery_ms'],[3,4,6,8]):d.append({'seed':seed,'case':'frequency24','phase':'recovery','pulse':-1,'rest_ms':t,'aBN1':y})
            trains.append({'seed':seed,'case':'fast24',**train_metrics([8,6,3]+[0]*21)})
            for t,y in zip(spec['recovery_ms'],[1,3,6,8]):profiles.append({'seed':seed,'case':'fast24','rest_ms':t,'aBN1':y})
        scores,_,_=frequency_scores(pd.DataFrame(d),pd.DataFrame(trains),pd.DataFrame(profiles),spec)
        self.assertTrue(all(s['eligible'] for s in scores));self.assertTrue(all(not s['supported'] for s in scores))

    def test_schedule_partial(self):
        rows=expected_schedule('partial',{**SPEC,'between_cycles_ms':2000.})
        r=[x for x in rows if x['kind']=='response'];self.assertEqual(len(r),36)
        firsts=[x['onset_s'] for x in r if x['pulse']==0]
        self.assertEqual(firsts,[0.,7.8,15.6])

    def test_partial_recovery_has_separate_screen(self):
        from analyze import partial_scores,pd
        rows=[]
        values=[[8,6,3,2,1,1,0,0,0,0,0,0],[5,3,1,0,0,0,0,0,0,0,0,0],[5,3,1,0,0,0,0,0,0,0,0,0]]
        for seed in SPEC['seeds']:
            for block,v in enumerate(values,1):
                rows.extend({'seed':seed,'phase':'train','block':block,'pulse':i,'aBN1':y} for i,y in enumerate(v))
        scores,_=partial_scores(pd.DataFrame(rows),SPEC)
        self.assertTrue(all(x['supported'] for x in scores))
        self.assertEqual(scores[0]['half_trial_own_baseline'],[3,3,3])
        self.assertEqual(scores[0]['half_trial_common_baseline'],[3,2,2])

    def test_h8_does_not_require_B_readout(self):
        from analyze import novel_scores,pd
        rows=[]
        for seed in SPEC['seeds']:
            def add(case,phase,y,pulse=-1,noninput=0):
                rows.append({'seed':seed,'case':case,'phase':phase,'aBN1':y,'pulse':pulse,'noninput_spikes':noninput})
            add('novel','naive_A',8);add('novel','sham_A',2)
            for i,y in enumerate([8,6,3,2,1,1,0,0,0,0,0,0]):add('novel_train','train',y,i)
            for B in SPEC['B_populations']:
                add(B,'naive_B',0,noninput=150);add(B,'trained_B',0,noninput=150)
                add(B,'naive_after_B',8);add(B,'trained_after_B',4);add(B,'blank_after_B',0)
        scores=novel_scores(pd.DataFrame(rows),SPEC)
        self.assertTrue(all(not x['eligible'] for x in scores if x['hallmark']=='H7'))
        self.assertTrue(all(x['supported'] for x in scores if x['hallmark']=='H8'))

    def test_schedule_novel(self):
        r=[x for x in expected_schedule('novel',SPEC) if x['kind']=='response'];self.assertEqual(len(r),24)
        for x in r:
            if x['phase'] in ['trained_after_B','sham_A']:self.assertAlmostEqual(x['onset_s'],6.5)
            if x['phase'] in ['naive_after_B','naive_A','blank_after_B']:self.assertAlmostEqual(x['onset_s'],.5)


if __name__=='__main__':unittest.main()
