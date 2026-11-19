import unittest
from test_phase7 import Base


class SimulationActionTests(Base):
    def test_action_reaches_management_and_cannot_be_decided_twice(self):
        from ortak.simulasyon_aksiyonlari import submit,list_actions,decide
        ident=submit(self.s,'2027-01','Personel alım önerisi','Kapasite açığı',[{'Ay':'2027-01','Senaryo':'Normal'}])
        self.assertEqual(list_actions(self.s)[0]['status'],'Onay bekliyor')
        self.s['profile']={'position':'manager','username':'manager1','full_name':'Yönetici'}
        self.assertEqual(decide(self.s,ident,True,'Uygun'),'Onaylandı')
        with self.assertRaises(ValueError):decide(self.s,ident,True,'Tekrar')


class InverseErlangTests(unittest.TestCase):
    def test_more_agents_support_more_calls_at_same_service_level(self):
        from ortak.senaryolar import inverse_erlang_calls
        self.assertGreater(inverse_erlang_calls(20,300,.8,20),inverse_erlang_calls(10,300,.8,20))


if __name__=='__main__':unittest.main()
