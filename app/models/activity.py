from app import db


class ActivityMixin(object):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime)
    type = db.Column(db.String)
    source = db.Column(db.String)
    tags = db.Column(db.String)
    last_updated = db.Column(db.DateTime)


class CongressVote(ActivityMixin, db.Model):
    __tablename__ = 'congress_vote'

    candidate_id = db.Column(db.String)
    category = db.Column(db.String)
    vote_id = db.Column(db.String)
    vote_status = db.Column(db.String)
    chamber = db.Column(db.String)
    result = db.Column(db.String)
    bill_id = db.Column(db.String)
    memo = db.Column(db.String)

    activity_type = "congress_vote"
    source_file_regexs = ["data.json"]


class CongressBillAction(ActivityMixin, db.Model):
    __tablename__ = 'congress_bill_action'

    bill_id = db.Column(db.String)
    text = db.Column(db.String)
    congress = db.Column(db.Integer)
    action_type = db.Column(db.String)

    activity_type = "congress_bill_action"
    source_file_regexs = ["data.json"]


class CongressBill(ActivityMixin, db.Model):
    __tablename__ = 'congress_bill'

    bill_id = db.Column(db.String)
    bill_type = db.Column(db.String)
    number = db.Column(db.Integer)
    congress = db.Column(db.Integer)
    title = db.Column(db.String)
    subjects = db.Column(db.String)
    summary = db.Column(db.String)
    status = db.Column(db.String)
    sponsor = db.Column(db.String)
    cosponsors = db.Column(db.String)

    activity_type = "congress_bill"
    source_file_regexs = ["data.json"]



class LobbyDisclosure1(ActivityMixin, db.Model):
    __tablename__ = 'lobbying_disclosure_1'

    form_id = db.Column(db.String)
    client = db.Column(db.String)
    registrant = db.Column(db.String)
    senate_id = db.Column(db.String)
    house_id = db.Column(db.String)
    lobbyists = db.Column(db.String)
    specific_issues = db.Column(db.String)

    activity_type = "ld1"


class LobbyDisclosure2(ActivityMixin, db.Model):
    __tablename__ = 'lobbying_disclosure_2'

    form_id = db.Column(db.String)
    client = db.Column(db.String)
    registrant = db.Column(db.String)
    senate_id = db.Column(db.String)
    house_id = db.Column(db.String)
    lobbyists = db.Column(db.String)
    specific_issues = db.Column(db.String)
    income = db.Column(db.Float)
    expenses = db.Column(db.Float)

    activity_type = "ld2"

class LobbyDisclosure203(ActivityMixin, db.Model):
    __tablename__ = 'lobbying_disclosure_203'

    form_id = db.Column(db.String)
    client = db.Column(db.String)
    senate_id = db.Column(db.String)
    house_id = db.Column(db.String)
    lobbyist = db.Column(db.String)
    contribution_type = db.Column(db.String)
    amount = db.Column(db.Float)
    contributor_name = db.Column(db.String)
    recipient_name = db.Column(db.String)
    candidate_id = db.Column(db.Float)

    activity_type = "ld203"
    source_file_regexs = [r"\d+.xml"]


class ScheduleA(ActivityMixin, db.Model):
    __tablename__ = 'schedule_a'

    contributor_name = db.Column(db.String)
    amount = db.Column(db.Float)
    record_id = db.Column(db.Integer)
    committee_id = db.Column(db.String)
    indicator = db.Column(db.String)
    image_num = db.Column(db.String)
    transaction_type = db.Column(db.String)
    entity_type = db.Column(db.String)
    file_num = db.Column(db.Integer)
    transaction_id = db.Column(db.String)
    other_id = db.Column(db.String)
    memo = db.Column(db.String)

    activity_type = "schedule_a"


class ScheduleB(ActivityMixin, db.Model):
    __tablename__ = 'schedule_b'

    contributor_name = db.Column(db.String)
    amount = db.Column(db.Float)
    candidate_id = db.Column(db.String)
    record_id = db.Column(db.Integer)
    committee_id = db.Column(db.String)
    indicator = db.Column(db.String)
    image_num = db.Column(db.String)
    transaction_type = db.Column(db.String)
    entity_type = db.Column(db.String)
    file_num = db.Column(db.Integer)
    transaction_id = db.Column(db.String)
    other_id = db.Column(db.String)
    memo = db.Column(db.String)

    activity_type = "schedule_b"
    source_file_regexs = [r"itpas2.txt"]


class ActivityFeedback(db.Model):
    """Tracks the feedback of the activities."""
    __tablename__ = 'activity_feedback'

    id = db.Column(db.Integer, primary_key=True)
    up_votes = db.Column(db.Integer)
    down_votes = db.Column(db.Integer)

"""
class ActivityTag(db.Model):
    """Tracks the feedback of the activities."""
    __tablename__ = 'activity_tag'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String)
    tag = db.Column(db.String)
"""