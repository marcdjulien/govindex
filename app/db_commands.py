import datetime
import glob
import json
import os
import re
import xmltodict
import string
from dateutil import parser
import sys
import hashlib

from app.models.activity import Result, Tag, LocalFile


DATE_FMT = "%m/%d/%Y, %H:%M:%S"

FILE_BUF_SIZE = 65536

FILE_HASH_CACHE = {}


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

def hash_file(filepath):
    md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        while True:
            data = f.read(FILE_BUF_SIZE)
            if not data:
                break
            md5.update(data)
    return md5.hexdigest()

def get_new_files(filepaths):
    new_files = []
    for filepath in filepaths:
        hash_code = hash_file(filepath)
        if LocalFile.query.filter(LocalFile.file_path==filepath)\
                          .filter(LocalFile.file_hash==hash_code)\
                          .count() == 0:
            new_files.append(filepath)
            FILE_HASH_CACHE[filepath] = hash_code
        else:
            print(f"Already parsed {filepath}")
    return new_files


def create_result(info):
    return Result(
        date=info["date"],
        type=info["type"],
        source=info["source"],
        tags=info["tags"],
        last_updated=info["last_updated"],
        details=info["details"]
    )


def publish_ld1s(db, source_dir, id_maps):
    filepaths, invalid_filepaths = get_files(source_dir, [r"\d+.xml"])
    assert filepaths, "No files found"

    filepaths = get_new_files(filepaths)

    print("The following files were invald:")
    for filepath in invalid_filepaths:
        print(f"    -{filepath}")

    n = 0
    for filepath in filepaths:
        with open(filepath, "r") as f:
            try:
                doc = xmltodict.parse(f.read())
                info = json.loads(json.dumps(doc))["LOBBYINGDISCLOSURE1"]

                # Figure out the date
                try:
                    date_info = info["effectiveDate"]
                    date = parser.parse(date_info)
                except Exception:
                    try:
                        date_info = info["signedDate"]
                        date = parser.parse(date_info)
                    except Exception as e:
                        print(f"Unable to determine date for {filepath}")
                        print(e)
                        date_info = "01011900"
                        date = datetime.datetime.strptime(date_info, "%m%d%Y")

                base_info = {
                    "form_id": os.path.basename(filepath).split('.')[0],
                    "client": info["clientName"],
                    "senate_id": info["senateID"] or "",
                    "house_id": info["houseID"] or "",
                    "specific_issues": info["specific_issues"],
                    "date": date.strftime(DATE_FMT)
                }

                for lobbyist_info in info["lobbyists"].get("lobbyist", []):
                    person_info = {}
                    name = " ".join(
                        lobbyist_info[name_part]
                        for name_part in ["lobbyistFirstName", "lobbyistLastName", "lobbyistSuffix"]
                        if lobbyist_info[name_part] is not None
                    )
                    if not name:
                        continue
                    person_info["name"] = name
                    person_info["covered_positions"] = lobbyist_info["coveredPosition"] or ""

                    if info["organizationName"] is not None:
                        person_info["registrant"] = info["organizationName"]
                    else:
                        person_info["registrant"] = person_info["name"]

                    tags = list(base_info.values()) + list(person_info.values())
                    tags.extend([
                        info["registrantGeneralDescription"] or "",
                        info["clientGeneralDescription"] or "",
                        "ld1", "ld-1", "ld",
                        "lobby filing",
                        "registration"
                    ])

                    details = {
                        "form_id": base_info["form_id"],
                        "registrant": person_info["registrant"],
                        "client": base_info["client"],
                        "senate_id": base_info["senate_id"],
                        "house_id": base_info["house_id"],
                        "lobbyist_name": person_info["name"],
                        "specific_issues": base_info["specific_issues"],
                        "covered_positions": person_info["covered_positions"]
                    }

                    final_info = {
                        "date": date,
                        "type": "ld1",
                        "source": "https://disclosurespreview.house.gov/ld/ldxmlrelease/{}/{}/{}".format(
                            info["reportYear"],
                            info["reportType"],
                            os.path.basename(filepath)
                        ),
                        "tags": ",".join(tags),
                        "details": json.dumps(details),
                        "last_updated": datetime.datetime.now(),
                    }

                    db.session.add(create_result(final_info))

                    n += 1
                    if n % 1000 == 0:
                        print(f"Parsed {n} records")

            except Exception as e:
                print(f"Failed to parse file {filepath}")
                print(e)
                raise
                continue
        db.session.add(LocalFile(file_path=filepath,
                                 file_hash=FILE_HASH_CACHE[filepath],
                                 date_parsed=datetime.datetime.now()))

    db.session.commit()
    print(f"Uploaded {n} records")


def publish_ld2s(db, source_dir, id_maps):
    filepaths, invalid_filepaths = get_files(source_dir, [r"\d+.xml"])
    assert filepaths, "No files found"

    filepaths = get_new_files(filepaths)

    print("The following files were invald:")
    for filepath in invalid_filepaths:
        print(f"    -{filepath}")

    failed = []

    n = 0
    for filepath in filepaths:
        with open(filepath, "r") as f:
            try:
                doc = xmltodict.parse(f.read())
                info = json.loads(json.dumps(doc))["LOBBYINGDISCLOSURE2"]

                # Figure out the date
                try:
                    # TODO: LD-2s don't have effective date
                    date_info = info["effectiveDate"]
                    date = parser.parse(date_info)
                except Exception:
                    try:
                        date_info = info["signedDate"]
                        date = parser.parse(date_info)
                    except Exception as e:
                        print(f"Unable to determine date for {filepath}")
                        print(e)
                        date_info = "01011900"
                        date = datetime.datetime.strptime(date_info, "%m%d%Y")

                alis = info["alis"]["ali_info"]
                if isinstance(alis, dict):
                    alis = [alis]

                for ali in alis:
                    base_info = {
                        "form_id": os.path.basename(filepath).split('.')[0],
                        "client": info["clientName"],
                        "income": info["income"],
                        "expenses": info["expenses"],
                        "termination_date": info["terminationDate"],
                        "senate_id": info["senateID"] or "",
                        "house_id": info["houseID"] or "",
                        "issue_code": ali["issueAreaCode"],
                        "specific_issues": ali["specific_issues"]["description"],
                        "federal_agencies": ali.get("federal_agencies", ""),
                        "date": date.strftime(DATE_FMT)
                    }

                    lobbyist_names = []
                    for lobbyist_info in ali["lobbyists"].get("lobbyist", []):
                        name = " ".join(
                            lobbyist_info[name_part]
                            for name_part in ["lobbyistFirstName", "lobbyistLastName", "lobbyistSuffix"]
                            if lobbyist_info[name_part] is not None
                        )
                        if not name:
                            continue
                        lobbyist_names.append(name)

                    base_info["lobbyist_names"] = ",".join(lobbyist_names)

                    if info["organizationName"] is not None:
                        base_info["registrant"] = info["organizationName"]
                    elif lobbyist_names:
                        base_info["registrant"] = lobbyist_names[0]
                    elif info["printedName"] is not None:
                        base_info["registrant"] = info["printedName"]
                    else:
                        base_info["registrant"] = "[No-Name]"


                    tags = list(base_info.values())
                    tags.extend([
                        "ld2", "ld-2", "ld",
                        "lobby filing",
                        "registration"
                    ])

                    details = {
                        "form_id": base_info["form_id"],
                        "registrant": base_info["registrant"],
                        "client": base_info["client"],
                        "senate_id": base_info["senate_id"],
                        "house_id": base_info["house_id"],
                        "lobbyist_names": base_info["lobbyist_names"],
                        "specific_issues": base_info["specific_issues"],
                        "income": base_info["income"],
                        "expenses": base_info["expenses"],
                        "termination_date": base_info["termination_date"],
                        "issue_code": base_info["issue_code"],
                        "federal_agencies": base_info["federal_agencies"],
                    }

                    final_info = {
                        "date": date,
                        "type": "ld2",
                        "source": "https://disclosurespreview.house.gov/ld/ldxmlrelease/{}/{}/{}".format(
                            info["reportYear"],
                            info["reportType"],
                            os.path.basename(filepath)
                        ),
                        "tags": ",".join([t for t in tags if t is not None]),
                        "details": json.dumps(details),
                        "last_updated": datetime.datetime.now(),
                    }

                    db.session.add(create_result(final_info))
                    n += 1


            except Exception as e:
                #print(f"Failed to parse file {filepath}")
                print(e)
                #raise
                failed.append(filepath)
                continue
        db.session.add(LocalFile(file_path=filepath,
                                 file_hash=FILE_HASH_CACHE[filepath],
                                 date_parsed=datetime.datetime.now()))

        if n % 1000 == 0:
            print(f"Parsed {n} records")
            db.session.commit()

    db.session.commit()
    print("Failed to parse the following:")
    for f in failed:
        print(f)
    print(f"Uploaded {n} records")


def publish_ld203s(db, source_dir, id_maps):
    filepaths, invalid_filepaths = get_files(source_dir, [r"\d+.xml"])
    assert filepaths, "No files found"

    filepaths = get_new_files(filepaths)

    print("The following files were invald:")
    for filepath in invalid_filepaths:
        print(f"    -{filepath}")

    n = 1
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
                    if contribution["date"] is None:
                        continue
                    contribution_info = {
                        "type": contribution["type"],
                        "amount": contribution["amount"].replace(",", ""),
                        "contributor_name": contribution["contributorName"],
                        "recipient_name": contribution["recipientName"],
                        "date": contribution["date"],
                    }

                    tags = list(contribution_info.values()) + list(base_info.values())
                    tags.extend([
                        contribution["payeeName"],
                        "ld203", "ld-203",
                        "lobby filing",
                        "contribution"
                    ])

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

                    details = {
                        "form_id": base_info["form_id"],
                        "client": base_info["client"],
                        "senate_id": base_info["senate_id"],
                        "house_id": base_info["house_id"],
                        "lobbyist": base_info["lobbyist"],
                        "contribution_type": contribution_info["type"],
                        "amount": contribution_info["amount"],
                        "contributor_name": contribution_info["contributor_name"],
                        "recipient_name": contribution_info["recipient_name"],
                    }

                    final_info = {
                        "date": date,
                        "type": "ld203",
                        "source": "https://disclosurespreview.house.gov/lc/lcxmlrelease/{}/{}/{}".format(
                            info["reportYear"],
                            info["reportType"],
                            os.path.basename(filepath)
                        ),
                        "tags": ",".join(tags),
                        "last_updated": datetime.datetime.now(),
                        "details": json.dumps(details)
                    }

                    db.session.add(create_result(final_info))

                    n += 1
                    if n % 1000 == 0:
                        print(f"Parsed {n} records")

            except Exception as e:
                print(f"Failed to parse file {filepath}")
                print(e)
                #raise
                continue

        db.session.add(LocalFile(file_path=filepath,
                                 file_hash=FILE_HASH_CACHE[filepath],
                                 date_parsed=datetime.datetime.now()))

    db.session.commit()
    print(f"Uploaded {n} records")


def publish_congress_votes(db, source_dir, id_maps):
    filepaths, invalid_filepaths = get_files(source_dir, ["data.json"])
    assert filepaths, "No files found"

    filepaths = get_new_files(filepaths)

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
                        tags.extend([
                            "vote",
                            "congress",
                            vote_status,
                            info.get("subject", "")

                        ])

                        cand_id = vote_info["id"]
                        if cand_id in id_maps["bioguide"]:
                            tags.extend(id_maps["bioguide"][cand_id]["name"]["official_full"].split())
                        if cand_id in id_maps["lis"]:
                            tags.extend(id_maps["lis"][cand_id]["name"]["official_full"].split())

                        details = {
                            "candidate_id": vote_info["id"],
                            "category": session_info["category"],
                            "vote_id": session_info["vote_id"],
                            "vote_status": vote_status,
                            "chamber": session_info["chamber"],
                            "result": session_info["result"],
                            "bill_id": session_info.get("bill_id", ""),
                            "memo": session_info["memo"],
                        }

                        final_info = {
                            "date": parser.parse(info["date"]),
                            "type": "congress_vote",
                            "source": info["source_url"],
                            "tags": ",".join(tags),
                            "last_updated": datetime.datetime.now(),
                            "details": json.dumps(details)
                        }

                        db.session.add(create_result(final_info))
                        n += 1
                        if n % 1000 == 0:
                            print(f"Parsed {n} records")

            except Exception as e:
                print(f"Failed to parse {filepath}")
                print(e)
                raise
                continue
        db.session.add(LocalFile(file_path=filepath,
                                 file_hash=FILE_HASH_CACHE[filepath],
                                 date_parsed=datetime.datetime.now()))

    db.session.commit()
    print(f"Upladed {n} records")


def publish_schdbs(db, source_dir, id_maps):
    filepaths, invalid_filepaths = get_files(source_dir, [r"itpas2.txt"])
    assert filepaths, "No files found"

    filepaths = get_new_files(filepaths)

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
                    tags.extend(["schedule_b", "schedule b", "fec", "contribution", "campaign"])
                    other_id = data[15]
                    cand_id = data[16]
                    committee_id = data[0]
                    if cand_id in id_maps["fec"]:
                        tags.extend(id_maps["fec"][cand_id]["name"]["official_full"].split())
                    if other_id in id_maps["fec"]:
                        tags.extend(id_maps["fec"][other_id]["name"]["official_full"].split())
                    if committee_id in id_maps["committee"]:
                        tags.extend(id_maps["committee"][committee_id].split())

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

                    details = {
                        "contributor_name": data[7],
                        "amount": data[14],
                        "candidate_id": data[16],
                        "record_id": data[21],
                        "committee_id": data[0],
                        "indicator": data[1],
                        "image_num": data[4],
                        "transaction_type": data[5],
                        "entity_type": data[6],
                        "file_num": data[18],
                        "transaction_id": data[17],
                        "other_id": data[15],
                        "memo": data[20]
                    }

                    final_info = {
                        "date": date,
                        "type": "schedule_b",
                        "source": "https://docquery.fec.gov/cgi-bin/fecimg/?{}".format(data[4]),
                        "tags": ",".join(tags),
                        "last_updated": datetime.datetime.now(),
                        "details": json.dumps(details)
                    }

                    db.session.add(create_result(final_info))

                    n += 1
                    if n % 1000 == 0:
                        print(f"Parsed {n} records")

                except Exception as e:
                    print(f"Failed to parse line {line_n} in {filepath}")
                    print(e)
                    continue
        db.session.add(LocalFile(file_path=filepath,
                                 file_hash=FILE_HASH_CACHE[filepath],
                                 date_parsed=datetime.datetime.now()))

        db.session.commit()
        print(f"Upladed {n} records")


def publish_congress_bills():
    pass

def publish_congress_bill_actions():
    pass

COMMIT_N = 1000000

def publish_tags(db):
    # Current count for commiting to the database
    commit_i = 0

    print(f"Tagging results ... ")
    # TODO: Memory intensize
    entries = Result.query.all()
    n_total = len(entries)
    for i, entry in enumerate(entries):
        print(f"{i+1}/{n_total}")
        pre_keywords = set(
            kw.lower()
            for kw in " ".join(entry.tags.split(",")).split()
        )
        keywords = set()
        for kw in pre_keywords:
            if kw[0] in string.punctuation:
                kw = kw[1::]
            if not kw:
                continue
            if kw[-1] in string.punctuation:
                kw = kw[:-1:]
            if not kw:
                continue
            keywords.add(kw)

        for kw in keywords:
            new_tag_entry = Tag(
                result_id=entry.id,
                keyword=kw
            )

            db.session.add(new_tag_entry)
            commit_i += 1

        if commit_i >= COMMIT_N:
            commit_i = 0
            db.session.commit()
            print("COMMIT!")

    db.session.commit()


PUBLISH_MAP = {
    "schedule_b": publish_schdbs,
    "ld1": publish_ld1s,
    "ld2": publish_ld2s,
    "ld203": publish_ld203s,
    "congress_vote": publish_congress_votes,
    "congress_bill_action": publish_congress_bill_actions,
    "congress_bill": publish_congress_bills,
}


def publish(db, filename, id_map):
    with open(filename, "r") as f:
        for line in f:
            line = line.strip().split("#")[0]
            if not line:
                continue
            print (line)
            data_type, dir_path = line.split()
            PUBLISH_MAP[data_type](db, dir_path, id_map)