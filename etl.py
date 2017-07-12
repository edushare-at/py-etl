#!/usr/bin/python3

import os
import pyodbc

from argparse         import ArgumentParser
from csv              import writer
from ldap3            import Server, Connection, SCHEMA, BASE, LEVEL
from ldap3            import ALL_ATTRIBUTES, DEREF_NEVER
from datetime         import datetime

def log (msg) :
    """ FIXME: We want real logging someday """
    print (msg)
# end def log

class LDAP_Access (object) :

    def __init__ (self, args) :
        self.args  = args
        self.srv   = Server (self.args.uri, get_info = SCHEMA)
        self.ldcon = Connection \
            (self.srv, self.args.bind_dn, self.args.password)
        self.ldcon.bind ()
       # FIXME: Poor-mans logger for now
        self.log = Namespace ()
        self.log ['debug'] = self.log ['error'] = log
    # end def __init__

    def get_entry (self, pk_uniqueid) :
        r = self.ldcon.search \
            ( self.args.base_dn, '(phonlineUniqueId=%s)' % pk_uniqueid
            , search_scope = LEVEL
            , attributes   = ALL_ATTRIBUTES
            )
        if r :
            if len (self.ldcon.response) != 1 :
                self.log.error \
                    ( "Got more than one record with pk_uniqueid %s"
                    % pk_uniqueid
                    )
            return self.ldcon.response [0]
    # end def get_entry

    def __getattr__ (self, name) :
        """ Delegate to our ldcon, caching variant """
        if name.startswith ('_') :
            raise AttributeError (name)
        r = getattr (self.ldcon, name)
        setattr (self, name, r)
        return r
    # end def __getattr__

# end class LDAP_Access

class Namespace (dict) :
    def __getattr__ (self, key) :
        try :
            return self [key]
        except KeyError as ke :
            raise AttributeError (ke)
    # end def __getattr__
# end class Namespace

def from_db_date (item) :
    """ Note that phonline stores the only date attribute
        "phonlineGebDatum" as a string!
    """
    return item.strftime ("%Y-%m-%d %H:%M:%S")
# end def from_db_date

def from_db_number (item) :
    if item is None :
        return item
    return str (int (item))
# end def from_db_number

class ODBC_Connector (object) :

    fields = dict \
        ( benutzer_alle_dirxml_v =
            ( 'person_nr_obf'
            , 'st_person_nr_obf'
            , 'org_einheiten'
            , 'emailadresse_b'
            , 'emailadresse_st'
            , 'bpk'
            , 'pm_sap_personalnummer'
            , 'schulkennzahlen'
            , 'funktionen'
            , 'pk_uniqueid'
            , 'vorname'
            , 'nachname'
            , 'benutzername'
            , 'passwort'
            , 'benutzergruppen'
            , 'aktiv_st_person'
            , 'aktiv_a_person'
            , 'aktiv_b_person'
            , 'chipid_b'
            , 'chipid_st'
            , 'chipid_a'
            , 'mirfareid_b'
            , 'mirfareid_st'
            , 'mirfareid_a'
            , 'matrikelnummer'
            , 'account_status_b'
            , 'account_status_st'
            , 'account_status_a'
            , 'geburtsdatum'
            , 'person_nr'
            , 'st_person_nr'
            , 'ident_nr'
            )
        , eventlog_ph =
            ( 'record_id'
            , 'table_key'
            , 'status'
            , 'event_type'
            , 'event_time'
            , 'perpetrator'
            , 'table_name'
            , 'column_name'
            , 'old_value'
            , 'new_value'
            , 'synch_id'
            , 'synch_online_flag'
            , 'transaction_flag'
            , 'read_time'
            , 'error_message'
            , 'attempt'
            , 'admin_notify_flag'
            )
        )
    odbc_to_ldap_field = dict \
        ( account_status_a      = 'phonlineAccStWeiterbildung'
        , account_status_b      = 'phonlineAccStBediensteter'
        , account_status_st     = 'phonlineAccStStudent'
        , aktiv_a_person        = 'phonlineWeiterbildungAktiv'
        , aktiv_b_person        = 'phonlineBediensteterAktiv'
        , aktiv_st_person       = 'phonlineStudentAktiv'
        , benutzergruppen       = 'phonlineBenutzergruppe'
        , benutzername          = 'cn'
        , bpk                   = 'phonlineBPK'
        , chipid_a              = 'phonlineChipIDWeiterbildung'
        , chipid_b              = 'phonlineChipIDBediensteter'
        , chipid_st             = 'phonlineChipIDStudent'
        , emailadresse_b        = 'phonlineEmailBediensteter'
        , emailadresse_st       = 'phonlineEmailStudent'
        , funktionen            = 'phonlineFunktionen'
        , geburtsdatum          = 'phonlineGebDatum'
        , ident_nr              = 'phonlineIdentNr'
        , matrikelnummer        = 'phonlineMatrikelnummer'
        , mirfareid_a           = 'phonlineMirfareIDWeiterbildung'
        , mirfareid_b           = 'phonlineMirfareIDBediensteter'
        , mirfareid_st          = 'phonlineMirfareIDStudent'
        , nachname              = 'sn'
        , org_einheiten         = 'phonlineOrgEinheiten'
        , passwort              = 'nspmDistributionPassword'
        , person_nr             = 'phonlinePersonNr'
        , person_nr_obf         = 'phonlinePersonNrOBF'
        , pk_uniqueid           = 'phonlineUniqueId'
        , pm_sap_personalnummer = 'phonlineSapPersnr'
        , schulkennzahlen       = 'phonlineSchulkennzahlen'
        , st_person_nr          = 'phonlinePersonNrStudent'
        , st_person_nr_obf      = 'phonlinePersonNrOBFStudent'
        , vorname               = 'givenName'
        )

    data_conversion = dict \
        ( geburtsdatum = from_db_date
        , ident_nr     = from_db_number
        , person_nr    = from_db_number
        , st_person_nr = from_db_number
        , pk_uniqueid  = from_db_number
        )

    def __init__ (self, args) :
        self.cnx    = pyodbc.connect (DSN = 'oracle')
        self.cursor = self.cnx.cursor ()
        self.args   = args
        self.table  = args.table.lower ()
        if self.args.action != 'csv' :
            self.ldap  = LDAP_Access (self.args)
            self.table = 'benutzer_alle_dirxml_v'
       # FIXME: Poor-mans logger for now
        self.log = Namespace ()
        self.log ['debug'] = self.log ['error'] = log
    # end def __init__

    def action (self) :
        if self.args.action == 'csv' :
            self.as_csv ()
        elif self.args.action == 'initial_load' :
            self.initial_load ()
        else :
            self.etl ()
    # end def action

    def as_csv (self) :
        """ Get table into a csv file. If a time is given, we only
            select the relevant table rows from the eventlog_ph table
            and then select the relevant rows from the
            benutzer_alle_dirxml_v table.
        """
        fields = self.fields [self.table]
        where  = ''
        fn     = self.args.output_file
        if not fn :
            fn = self.table
        if self.args.time :
            t     = self.args.time.replace ('.', ' ')
            fmt   = 'YYYY-MM-DD HH:MI:SS'
            where = "where event_time > to_date ('%s', '%s')" % (t, fmt)
            fn    = fn + '.' + self.args.time.replace (' ', '.')
        if not fn.endswith ('.csv') :
            fn = fn + '.csv'
        ids = []
        with open (fn, 'w', encoding = 'utf-8') as f :
            w = writer (f, delimiter = self.args.delimiter)
            w.writerow (fields)
            self.cursor.execute \
                ( 'select %s from %s %s'
                % (','.join (fields), self.table, where)
                )
            for row in self.cursor :
                w.writerow (row)
                ids.append (row [1].split ('=') [1])
        if self.args.time and ids :
            tbl = self.table
            fn  = tbl + '.' + self.args.time.replace (' ', '.') + '.csv'
            fields = self.fields [tbl]
            where  = "where pk_uniqueid in (%s)" % ','.join (ids)
            with open (fn, 'w', encoding = 'utf-8') as f :
                w = writer (f, delimiter = self.args.delimiter)
                w.writerow (fields)
                self.cursor.execute \
                    ( 'select %s from %s %s'
                    % (','.join (fields), tbl, where)
                    )
                for row in self.cursor :
                    w.writerow (row)
    # end def as_csv

    def initial_load (self) :
        tbl    = self.table
        fields = self.fields [tbl]
        self.cursor.execute \
            ('select %s from %s where pk_uniqueid = 115278' % (','.join (fields), self.table))
        for row in self.cursor :
            self.sync_to_ldap (row, is_new = True)
    # end def initial_load

    def sync_to_ldap (self, row, is_new = False) :
        """ Sync a single record to LDAP. We return an error message if
            something goes wrong (and log the error). The caller might
            want to put the error message into some table in the
            database.
        """
        tbl = self.table
        rw  = Namespace ((k, row [i]) for i, k in enumerate (self.fields [tbl]))
        if not rw.pk_uniqueid :
            # FIXME: Do we want to log user data here??
            self.log.error ("Got User without pk_uniqueid")
            return
        # Find pk_uniqueid in LDAP phonlineUniqueId
        uid   = self.to_ldap (rw.pk_uniqueid, 'pk_uniqueid')
        ldrec = self.ldap.get_entry (uid)
        if ldrec :
            if is_new :
                # Log an error but continue like a normal sync
                self.log.error \
                    ( 'Found pk_uniqueid "%s" when sync says it should be new'
                    % uid
                    )
            ld_update = {}
            ld_delete = {}
            for k in rw :
                v  = self.to_ldap (rw [k], k)
                lk = self.odbc_to_ldap_field [k]
                lv = ldrec ['attributes'].get (lk, None)
                if v == lv or [v] == lv :
                    continue
                if v is None :
                    ld_delete [lk] = None
                else :
                    ld_update [lk] = v
            # dn modified, the cn is the rdn!
            #if 'cn' in ld_update :
            #    self.ldap.modify_dn (ldrec.cn,
        else :
            if not is_new :
                # Log an error but continue like a normal sync
                self.log.error \
                    ( 'pk_uniqueid "%s" not found, sync says it exists'
                    % uid
                    )
            ld_update = {}
            for k in rw :
                lk = self.odbc_to_ldap_field [k]
                v  = self.to_ldap (rw [k], k)
                if v is not None :
                    ld_update [lk] = v
            ld_update ['objectClass'] = ['inetOrgPerson', 'phonlinePerson']
            r = self.ldap.add \
                ( ('cn=%s,' % ld_update ['cn']) + self.args.base_dn
                , attributes = ld_update
                )
            if not r :
                msg = \
                    ( "Error on LDAP add: %(description)s: %(message)s"
                      " (code: %(result)s)"
                    % self.ldap.result
                    )
                self.log.error (msg)
                return msg
    # end def sync_to_ldap

    def to_ldap (self, item, dbkey) :
        conv = self.data_conversion.get (dbkey)
        if conv :
            return conv (item)
        return item
    # end def to_ldap

# end class ODBC_Connector

def main () :
    cmd = ArgumentParser ()
    cmd.add_argument \
        ( 'action'
        , help    = 'Action to perform, one of "csv", "initial_load", "etl"'
        )
    cmd.add_argument \
        ( "-B", "--bind-dn"
        , help    = "Bind-DN, default=%(default)s"
        , default = "cn=admin,o=BMUKK"
        )
    # FIXME: We want some magic for specifying instance automatically
    cmd.add_argument \
        ( "-d", "--base-dn"
        , help    = "Base-DN for starting search, default=%(default)s"
        , default = 'ou=user,ou=ph08,o=BMUKK'
        )
    cmd.add_argument \
        ( '-D', '--delimiter'
        , help    = 'Delimiter of csv file, default=%(default)s'
        , default = ';'
        )
    cmd.add_argument \
        ( '-o', '--output-file'
        , help    = 'Output file for writing CSV, default is table name'
        )
    cmd.add_argument \
        ( "-P", "--password"
        , help    = "Password for binding"
        , default = 'changeit'
        )
    # Compute the default ldap server from environment of container
    # In production we'll have an argument here
    default_ldap = os.environ.get ('8389_PORT').replace ('tcp', 'ldap')
    cmd.add_argument \
        ( '-u', '--uri'
        , help    = "LDAP uri, default=%(default)s"
        , default = default_ldap
        )
    # -t (table) and -T (time) are mutually exclusive: We dump out both
    # relevant tables if the -T option is given.
    group = cmd.add_mutually_exclusive_group ()
    group.add_argument \
        ( '-t', '--table'
        , help    = 'Table name, default=%(default)s'
        , default = 'eventlog_ph'
        )
    group.add_argument \
        ( '-T', '--time'
        , help    = 'Cut-off time for eventlog, if specified, both the '
                    'eventlog_ph *and* the benutzer_alle_dirxml_v are '
                    'dumped but only records newer than the given time.'
        )
    args = cmd.parse_args ()
    odbc = ODBC_Connector (args)
    odbc.action ()
# end def main

if __name__ == '__main__' :
    main ()
