# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import click
from flask import Flask, url_for
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from importlib import import_module
from logging import basicConfig, DEBUG, getLogger, StreamHandler
import os
import yaml
from dateutil import parser


db = SQLAlchemy()
login_manager = LoginManager()

# Must be aster db is created.
from app.db_commands import (
    publish_schdbs,
    publish_ld203s,
    publish_congress_votes,
    publish_congress_bill_actions,
    publish_congress_bills,
)


CURRENT_LEGISLATORS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__name__)),
    "app",
    "data",
    "legislators-current.yaml"
)

EXECUTIVE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__name__)),
    "app",
    "data",
    "executive.yaml"
)

govtrack_ids = {}
lis_ids = {}
bioguide_ids = {}
fec_ids = {}

# For now, assuming legislators and executive are mutually exclusive
with open(CURRENT_LEGISLATORS_PATH, "r") as f1:
    with open(EXECUTIVE_PATH, "r") as f2:
        info = yaml.load(f1) + yaml.load(f2)
        govtrack_ids = {
            c["id"]["govtrack"]: {key: c[key] for key in c}
            for c in info
        }

        bioguide_ids = {
            c["id"]["bioguide"]: {key: c[key] for key in c}
            for c in info
            if "bioguide" in c["id"]
        }

        lis_ids = {
            c["id"]["lis"]: {key: c[key] for key in c}
            for c in info
            if "lis" in c["id"]
        }

        for profile in govtrack_ids.values():
            if "official_full" not in profile["name"]:
                name = []
                for key in ["first", "middle", "last"]:
                    name.append(profile["name"].get(key, ""))
                profile["name"]["official_full"] = " ".join(tok for tok in name if tok)

        # Map FEC ID to profile
        for gid in govtrack_ids:
            for fec_id in govtrack_ids[gid]["id"].get("fec", []):
                fec_ids[fec_id] = govtrack_ids[gid]


# Parse FEC info
# For now just 2020
# TODO: parse all years
with open("app/data/weball20.txt") as f:
    for line in f:
        data = line.split("|")
        fec_id = data[0]
        name = data[1]
        try:
            last, first = name.split(",", 1)
        except:
            try:
                last, first = name.split(" ", 1)
            except:
                full_name = name
                last = name
                first = name
        last = last.strip().capitalize()
        first = first.strip().capitalize()
        full_name = f"{first} {last}"

        if fec_id not in fec_ids:
            info = {
                "id": {"fec":[fec_id]},
                "name": {
                    "first":first,
                    "last":last,
                    "official_full": full_name
                }
            }
            fec_ids[fec_id] = info


# Parse FEC info
# For now just 2020
# TODO: parse all years
committee_ids = {}
with open("app/data/cm20.txt") as f:
    for line in f:
        data = line.split("|")
        fec_id = data[0]
        name = data[1]
        committee_ids[fec_id] = name


schedule_b_codes = {}
with open("app/data/schedule_b_codes.txt") as f:
    for line in f:
        data = line.split(" ", 1)
        schedule_b_codes[data[0].strip()] = data[1].strip()

def register_extensions(app):
    db.init_app(app)
    login_manager.init_app(app)

def register_blueprints(app):
    for module_name in ('base', 'home'):
        module = import_module('app.{}.routes'.format(module_name))
        app.register_blueprint(module.blueprint)

def configure_database(app):

    @app.before_first_request
    def initialize_database():
        db.create_all()

    @app.teardown_request
    def shutdown_session(exception=None):
        db.session.remove()

def register_commands(app):
    @app.cli.command("publish-data")
    @click.argument('type')
    @click.argument('source_dir')
    def publish_data(type, source_dir):
        """Publish data to the database."""
        type_to_func = {
            "schdb": publish_schdbs,
            "ld203": publish_ld203s,
            "congress_vote": publish_congress_votes,
            "congress_bill_action": publish_congress_bill_actions,
            "congress_bill": publish_congress_bills,
        }
        f = type_to_func.get(type)
        if f is None:
            print(f"Invalid type: {type}")
            return
        else:
            f(db, source_dir)

    app.cli.add_command(publish_data)

def register_filters(app):
    @app.template_filter('date')
    def date(d, fmt):
        return d.strftime(fmt) if d else "No Date"

    @app.template_filter('smart_find')
    def smart_find(id):
        for collection in [bioguide_ids, lis_ids, fec_ids]:
            if id in collection:
                return collection[id]["name"]["official_full"]
        return id

    @app.template_filter('bioguide_to_name')
    def bioguide_to_name(id):
        return bioguide_ids[id]["name"]["official_full"]

    @app.template_filter('fec_to_name')
    def fec_to_name(id):
        return fec_ids[id]["name"]["official_full"]

    @app.template_filter('committee_id_to_name')
    def committee_id_to_name(id):
        return committee_ids[id]

    @app.template_filter('schdb_code')
    def schdb_code(code):
        return schedule_b_codes.get(code)

    @app.template_filter('qurl')
    def query_url(query):
        return f"/index?gquery={query}"

    @app.template_filter('govtrack_url')
    def govtrack_url(bill_id):
        try:
            congress, bill = bill_id.split("-")
            return f"https://www.govtrack.us/congress/bills/{bill}/{congress}"
        except:
            return f"https://www.govtrack.us/search?q={bill_id}"

    @app.template_filter('vote_color')
    def vote_color(vote_status):
        mapping = {
            "cv-no": ["no", "nay"],
            "cv-yes": ["yes", "aye", "yea"],
            "cv-nv":["not voting"]
        }
        for theme, status in mapping.items():
            if vote_status.lower() in status:
                return theme
        return "cv-nv"


def create_app(config):
    app = Flask(__name__, static_folder='base/static')
    app.config.from_object(config)
    register_extensions(app)
    register_blueprints(app)
    register_commands(app)
    register_filters(app)
    configure_database(app)

    return app