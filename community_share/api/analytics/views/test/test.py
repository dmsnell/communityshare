import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from community_share import Base
from community_share.api.analytics.views.record_view import record_view
from community_share.models.analytics import PageView


class Store:
    engine = create_engine('sqlite:///:memory:')
    Session = sessionmaker(bind=engine)
    session = Session()


store = Store()


class PageViewTest(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(store.engine)
        Base.metadata.create_all(store.engine)

    def test_rejects_short_next_path(self):
        self.assertFalse(record_view(1, '', '/some/valid/path', store=store))

    def test_rejects_short_prev_path(self):
        self.assertFalse(record_view(1, '/some/valid/path', '', store=store))

    def test_rejects_non_strings(self):
        self.assertFalse(record_view(1, 1, '', store=store))

    def test_stores_page_view(self):
        record_view(1, '/next/path', '/prev/path', store=store)
        self.assertEqual(1, store.session.query(PageView).count())

    def test_stores_duplicates(self):
        record_view(1, '/next/path', '/prev/path', store=store)
        record_view(1, '/next/path', '/prev/path', store=store)
        self.assertEqual(2, store.session.query(PageView).count())


if __name__ == '__main__':
    unittest.main()
