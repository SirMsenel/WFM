"""Statüler doğru personel ve vardiya gününe bağlı kalır."""
import unittest
from ortak.statu_kartlari import status_cells

class StatusCalendarTests(unittest.TestCase):
 def test_overnight_status_stays_under_its_shift_day(self):
  items=[{'employee_id':'7','date':'2026-11-12','start':'2026-11-13 02:00:00','end':'2026-11-13 02:15:00','kind':'Mola','status':'Planlı'}]
  cells=status_cells(items,[{'employee_id':7}],'2026-11-12','2026-11-12');self.assertEqual(list(cells),[(0,'12.11 Perşembe')]);self.assertEqual(cells[(0,'12.11 Perşembe')],items)
 def test_canceled_other_person_and_outside_range_are_not_displayed(self):
  base={'employee_id':'7','start':'2026-11-12 12:00:00','end':'2026-11-12 12:30:00','kind':'Yemek','status':'Planlı'}
  values=[base,dict(base,status='İptal'),dict(base,employee_id='8'),dict(base,date='2026-11-11')]
  cells=status_cells(values,[{'employee_id':7}],'2026-11-12','2026-11-12');self.assertEqual(sum(map(len,cells.values())),1);self.assertEqual(next(iter(cells.values())),[base])
