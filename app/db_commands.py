import datetime
import glob
import json
import os
import re
import xmltodict
from dateutil import parser

from app.models.activity import (
    CongressBill,
    CongressBillAction,
    CongressVote,
    LobbyDisclosure1,
    LobbyDisclosure2,
    LobbyDisclosure203,
    ScheduleA,
    ScheduleB
)

# TODO: Create better primary keys instead of potential collisions with hashing

def hash_activity(info):
    return (
        hash(str(info["date"])) ^
        hash(info["type"]) ^
        hash(info["source"]) ^
        hash(info["tags"])
    )


def get_files(source_dir, filename_regexs):
    valid = []
    invalid = []
    for filepath in glob.glob(os.path.join(source_dir, "**"), recursive=True):
        if any(
            re.match(pattern, os.path.basename(filepath))
            for pattern in filename_regexs
        ):
            valid.append(filepath)
        else:
            invalid.append(filepath)
    return valid, invalid


def publish_schdbs(db, source_dir):
    filepaths, invalid_filepaths = get_files(source_dir, ScheduleB.source_file_regexs)
    assert filepaths, "No files found"

    print("The following files were invald:")
    for filepath in invalid_filepaths:
        print(f"    -{filepath}")

    n = 0
    for filepath in filepaths:
        with open(filepath, "r") as f:
            for i, line in enumerate(f):
                try:
                    line_n = i + 1

                    data = [tok.strip() for tok in line.split("|")]
                    if len(data) != 22:
                        raise ParseException("Failed to parse line {line_n} in {filepath}")

                    tags = [d.lower() for d in data if d]
                    tags.extend(["schedule b", "fec", "contribution"])

                    # Figure out the date
                    date_info = data[13]
                    try:
                        date = datetime.datetime.strptime(date_info, "%m%d%Y")
                    except ValueError:
                        try:
                            scan_num = data[4]
                            if len(scan_num) == 11:
                                assert scan_num[0:2].isdigit()
                                year = scan_num[0:2]
                                if 0 <= int(year) <= 60:
                                    date_info = "010120" + year
                                else:
                                    date_info = "010120" + year
                            elif len(scan_num) == 18:
                                assert scan_num[0:8].isdigit()
                                year = scan_num[0:4]
                                month = scan_num[4:6]
                                day = scan_num[6:8]
                                date_info = month + day + year
                        except Exception as e:
                            print(f"Unable to determine date for line {line_n}")
                            print(e)
                            date_info = "01011900"
                        date = datetime.datetime.strptime(date_info, "%m%d%Y")

                    common_info = {
                        "date": date,
                        "type": "schedule_b",
                        "source": "https://docquery.fec.gov/cgi-bin/fecimg/?{}".format(data[4]),
                        "tags": ",".join(tags)
                    }
                    new_entry = ScheduleB(
                        id=hash_activity(common_info),
                        date=date,
                        type=common_info["type"],
                        source=common_info["source"],
                        tags=common_info["tags"],
                        last_updated=datetime.datetime.now(),
                        contributor_name=data[7],
                        amount=data[14],
                        candidate_id=data[16],
                        record_id=data[21],
                        committee_id=data[0],
                        indicator=data[1],
                        image_num=data[4],
                        transaction_type=data[5],
                        entity_type=data[6],
                        file_num=data[18],
                        transaction_id=data[17],
                        other_id=data[15],
                        memo=data[20]
                    )
                    db.session.add(new_entry)
                    n += 1
                except Exception as e:
                    print(f"Failed to parse line {line_n} in {filepath}")
                    print(e)
                    continue

        db.session.commit()
        print(f"Upladed {n} records")


def publish_ld203s(db, source_dir):
    filepaths, invalid_filepaths = get_files(source_dir, LobbyDisclosure203.source_file_regexs)
    assert filepaths, "No files found"

    print("The following files were invald:")
    for filepath in invalid_filepaths:
        print(f"    -{filepath}")

    n = 0
    for filepath in filepaths:
        with open(filepath, "r") as f:
            try:
                doc = xmltodict.parse(f.read())
                info = json.loads(json.dumps(doc))["CONTRIBUTIONDISCLOSURE"]
                if info["noContributions"] is not None and info["noContributions"].lower() == "true":
                    continue

                base_info = {
                    "form_id": os.path.basename(filepath).split('.')[0],
                    "client": info["organizationName"],
                    "senate_id": info["senateRegID"],
                    "house_id": info["houseRegID"],
                }
                base_info["lobbyist"] = " ".join(
                    info[name_part]
                    for name_part in ["lobbyistFirstName", "lobbyistMiddleName", "lobbyistLastName", "lobbyistSuffix"]
                    if info[name_part] is not None
                )

                if info["contributions"] is None:
                    raise Exception("No contributions")

                if isinstance(info["contributions"]["contribution"], dict):
                    contributions = [info["contributions"]["contribution"]]
                else:
                    contributions = info["contributions"]["contribution"]

                for contribution in contributions:
                    contribution_info = {
                        "type": contribution["type"],
                        # TODO: Remove commas in all parsers
                        "amount": contribution["amount"].replace(",", ""),
                        "contributor_name": contribution["contributorName"],
                        "recipient_name": contribution["recipientName"],
                        "date": contribution["date"],
                    }

                    tags = list(contribution_info.values()) + list(base_info.values())
                    tags.extend([contribution["payeeName"], "ld203", "contribution"])

                    # Figure out the date
                    try:
                        date_info = contribution_info["date"]
                        date = parser.parse(date_info)
                    except Exception:
                        try:
                            date_info = base_info["signedDate"]
                            date = parser.parse(date_info)
                        except Exception as e:
                            print(f"Unable to determine date for {filepath}")
                            print(e)
                            date_info = "01011900"
                            date = datetime.datetime.strptime(date_info, "%m%d%Y")

                    common_info = {
                        "date": date,
                        "type": "ld203",
                        "source": "https://disclosurespreview.house.gov/lc/lcxmlrelease/{}/{}/{}".format(
                            info["reportYear"],
                            info["reportType"],
                            os.path.basename(filepath)
                        ),
                        "tags": ",".join(tags)
                    }
                    new_entry = LobbyDisclosure203(
                        # Not gauranteed to be unique
                        date=date,
                        type=common_info["type"],
                        source=common_info["source"],
                        tags=common_info["tags"],
                        last_updated=datetime.datetime.now(),
                        form_id=base_info["form_id"],
                        client=base_info["client"],
                        senate_id=base_info["senate_id"],
                        house_id=base_info["house_id"],
                        lobbyist=base_info["lobbyist"],
                        contribution_type=contribution_info["type"],
                        amount=contribution_info["amount"],
                        contributor_name=contribution_info["contributor_name"],
                        recipient_name=contribution_info["recipient_name"],
                        # TODO: Create task to fill in candidate names
                    )
                    db.session.add(new_entry)
                    n += 1
            except Exception as e:
                print(f"Failed to parse file {filepath}")
                print(e)
                continue

    db.session.commit()
    print(f"Uploaded {n} records")


def publish_congress_votes(db, source_dir):
    filepaths, invalid_filepaths = get_files(source_dir, CongressVote.source_file_regexs)
    assert filepaths, "No files found"

    print("The following files were invald:")
    for filepath in invalid_filepaths:
        print(f"    -{filepath}")

    n = 0
    for filepath in filepaths:
        with open(filepath, "r") as f:
            try:
                info = json.load(f)

                session_info = {
                    "vote_id": info["vote_id"],
                    "chamber": "house" if info["chamber"].lower() == "h" else "senate",
                    "result": info["result"],
                    "category": info["category"],
                    "memo": info["question"]
                }
                if "bill" in info:
                    session_info["bill_id"] = "{}{}-{}".format(info["bill"]["type"],
                                                               info["bill"]["number"],
                                                               info["bill"]["congress"])

                for vote_status in info["votes"]:
                    for vote_info in info["votes"][vote_status]:
                        tags = list(session_info.values()) + list(vote_info.values())
                        tags.extend(["vote", "congress", vote_status])

                        common_info = {
                            "date": parser.parse(info["date"]),
                            "type": "congress_vote",
                            "source": info["source_url"],
                            "tags": ",".join(tags)
                        }

                        new_entry = CongressVote(
                            id=hash_activity(common_info),
                            date=common_info["date"],
                            type=common_info["type"],
                            source=common_info["source"],
                            tags=common_info["tags"],
                            last_updated=datetime.datetime.now(),
                            candidate_id = vote_info["id"],
                            category = session_info["category"],
                            vote_id = session_info["vote_id"],
                            vote_status = vote_status,
                            chamber = session_info["chamber"],
                            result = session_info["result"],
                            bill_id = session_info.get("bill_id", ""),
                            memo = session_info["memo"],
                        )
                        db.session.add(new_entry)
                        n += 1
            except Exception as e:
                print(f"Failed to parse {filepath}")
                print(e)
                continue

    db.session.commit()
    print(f"Upladed {n} records")


def publish_congress_bill_actions(db, source_dir):
    filepaths, invalid_filepaths = get_files(source_dir, CongressBillAction.source_file_regexs)
    assert filepaths, "No files found"

    print("The following files were invald:")
    for filepath in invalid_filepaths:
        print(f"    -{filepath}")

    n = 0
    for filepath in filepaths:
        with open(filepath, "r") as f:
            try:
                info = json.load(f)

                for action in info["actions"]:
                    action_info = {
                        "text": action["text"],
                        "acted_at": action["acted_at"],
                        "type": action["type"],
                    }

                    tags = list(action_info.values())
                    tags.extend(["bill", "congress"])

                    if info["subjects_top_term"] is not None:
                        tags.append(info["subjects_top_term"])

                    # TODO: Figure out better tags
                    for title_info in info.get("titles", []):
                        tags.extend(title_info.get("title").split())

                    common_info = {
                        "date": parser.parse(action_info["acted_at"]),
                        "type": "congress_bill_action",
                        "source": info["url"],
                        "tags": ",".join(list(set(tags)))
                    }

                    new_entry = CongressBillAction(
                        # Not gauranteed to be unique
                        date=common_info["date"],
                        type=common_info["type"],
                        source=common_info["source"],
                        tags=common_info["tags"],
                        last_updated=datetime.datetime.now(),
                        bill_id = info["bill_id"],
                        text = action_info["text"],
                        congress = info["congress"],
                        action_type = action_info["type"]
                    )
                    db.session.add(new_entry)
                    n += 1
            except Exception as e:
                print(f"Failed to parse {filepath}")
                print(e)
                continue

    db.session.commit()
    print(f"Upladed {n} records")


def publish_congress_bills(db, source_dir):
    filepaths, invalid_filepaths = get_files(source_dir, CongressBill.source_file_regexs)
    assert filepaths, "No files found"

    print("The following files were invald:")
    for filepath in invalid_filepaths:
        print(f"    -{filepath}")

    n = 0
    for filepath in filepaths:
        with open(filepath, "r") as f:
            try:
                info = json.load(f)

                bill_info = {
                    "bill_id": info["bill_id"],
                    "bill_type": info["bill_type"],
                    "number": info["bill_type"],
                    "congress": info["congress"],
                    "summary": (info.get("summary") or {}).get("text", ""),
                    "status": info["status"],
                    "sponsor": info["sponsor"]["bioguide_id"],
                    "cosponsors": ",".join([c["bioguide_id"] for c in info["cosponsors"]]),
                }

                if isinstance(info["subjects"], list):
                    bill_info["subjects"] = ",".join(info["subjects"])

                for title_type in ["official_title", "short_title", "popular_title"]:
                    if info[title_type] is not None:
                        bill_info["title"] = info[title_type]
                        break

                if "title" not in bill_info:
                    raise Exception(f"Failed to find title for {filepath}")

                tags = list(bill_info.values())
                tags.extend(["bill", "congress"])


                # TODO: Figure out better tags
                for title_info in info.get("titles", []):
                    tags.extend(title_info.get("title").split())

                common_info = {
                    "date": parser.parse(info["introduced_at"]),
                    "type": "congress_bill",
                    "source": info["url"],
                    "tags": ",".join(list(set(tags)))
                }

                new_entry = CongressBill(
                    # Not gauranteed to be unique
                    date=common_info["date"],
                    type=common_info["type"],
                    source=common_info["source"],
                    tags=common_info["tags"],
                    last_updated=datetime.datetime.now(),
                    bill_id = bill_info["bill_id"],
                    bill_type = bill_info["bill_type"],
                    number = bill_info["number"],
                    congress = bill_info["congress"],
                    title = bill_info["title"],
                    subjects = bill_info["status"],
                    summary = bill_info["summary"],
                    status = bill_info["status"],
                    sponsor = bill_info["sponsor"],
                    cosponsors = bill_info["cosponsors"],
                )
                db.session.add(new_entry)
                n += 1
            except Exception as e:
                print(f"Failed to parse {filepath}")
                print(e)
                raise
                continue

    db.session.commit()
    print(f"Upladed {n} records")
