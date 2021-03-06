#   Copyright 2020 Martin Vogt, Antonio de la Vega de Leon
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
#  associated documentation files (the "Software"), to deal in the Software without restriction,
#  including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
#  and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do
#  so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
#  INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
#  PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
#  COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN
#  AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
#  WITH  THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import rdkit.Chem as Chem
import os.path
import pickle
from zlib import adler32
import logging
import pprint
import gzip
import sys

from rdkit.Chem.rdMolDescriptors import GetMACCSKeysFingerprint
from rdkit.Chem.rdMolDescriptors import GetAtomPairFingerprint
from rdkit.Chem.rdMolDescriptors import GetTopologicalTorsionFingerprint
from rdkit.Chem.rdMolDescriptors import GetMorganFingerprint
from rdkit.Chem.rdMolDescriptors import GetHashedAtomPairFingerprint
from rdkit.Chem.rdMolDescriptors import GetHashedTopologicalTorsionFingerprint
from rdkit.Chem.rdMolDescriptors import GetHashedMorganFingerprint
from rdkit.Avalon.pyAvalonTools import GetAvalonFP

from ccbmlib.statistics import PairwiseStats


# known_fps = {"RDKFingerprint":rdk}

# Functions for calculating different fingerprints
# All fingerprints are returned as lists of features

def rdkit_fingerprint(mol, **kwargs):
    return list(Chem.RDKFingerprint(mol, **kwargs).GetOnBits())


def maccs_keys(mol, **kwargs):
    return list(GetMACCSKeysFingerprint(mol).GetOnBits())


def atom_pairs(mol, **kwargs):
    return list(GetAtomPairFingerprint(mol, **kwargs).GetNonzeroElements())


def torsions(mol, **kwargs):
    return list(GetTopologicalTorsionFingerprint(mol, **kwargs).GetNonzeroElements())


def morgan(mol, **kwargs):
    return list(GetMorganFingerprint(mol, **kwargs).GetNonzeroElements())


def hashed_atom_pairs(mol, **kwargs):
    return list(GetHashedAtomPairFingerprint(mol, **kwargs).GetNonzeroElements())


def hashed_torsions(mol, **kwargs):
    return list(GetHashedTopologicalTorsionFingerprint(mol, **kwargs).GetNonzeroElements())


def hashed_morgan(mol, **kwargs):
    return list(GetHashedMorganFingerprint(mol, **kwargs).GetNonzeroElements())


def avalon(mol, **kwargs):
    return list(GetAvalonFP(mol, **kwargs).GetOnBits())


def tc(fp_a,fp_b):
    a=len(fp_a)
    b=len(fp_b)
    c=len(set(fp_a).intersection(fp_b))
    if c != 0:
        return c/(a+b-c)
    else:
        return 0

def generate_fingerprints(mol_suppl, fp, pars):
    for mol in mol_suppl:
        if mol:
            yield fp(mol, **pars)


def hash_parameter_set(pars):
    s = sorted(pars.items())
    return adler32(str(s).encode('UTF-8'))


def auto_open(fname, mode="rt"):
    if fname.endswith(".gz"):
        return gzip.open(fname, mode)
    else:
        return open(fname, mode)


def get_full_filename(filename):
    fname = os.path.join(_base_folder, filename)
    if os.path.exists(fname):
        return fname
    else:
        return fname + ".gz"


def get_fp_filename(db, fp, pars):
    exists = True
    count = ""
    while exists:
        fname = "{db}-{fp}-{par_hash}{suffix}.fp.txt".format(db=db, fp=fp, par_hash=hash_parameter_set(pars),
                                                             suffix=count)
        exists = os.path.exists(get_full_filename(fname))
        count = count - 1 if count else -1
    return fname


def get_stats_filename(db, fp, pars, limit):
    exists = True
    count = ""
    while exists:
        fname = "{db}-{fp}-{par_hash}{suffix}.stats-{limit}.pickle".format(db=db, fp=fp,
                                                                           par_hash=hash_parameter_set(pars),
                                                                           suffix=count,
                                                                           limit=limit)
        exists = os.path.exists(get_full_filename(fname))
        count = count - 1 if count else -1
    return fname

    return "{db}-{fp}-{par_hash}.stats-{limit}.pickle".format(db=db, fp=fp, par_hash=hash_parameter_set(pars),
                                                              limit=limit)


def get_fp_dictionary_key(db, fp, pars):
    par_key = frozenset(pars.items())
    return frozenset([("db", db), ("fp", fp), ("pars", par_key)])


def pickle_fp_dictionary():
    global _fp_dictionary
    with open(_fp_dictionary_pickle, "wb") as pf:
        pickle.dump(_fp_dictionary, pf, pickle.HIGHEST_PROTOCOL)


def to_key_val_string(pars):
    return " ".join("{}:{}".format(k, v) for k, v in sorted(pars.items()))


def get_fingerprints(db_name, fp_name, pars, get_mol_suppl= None):
    if not _initialized:
        raise Exception("Data folder not set. Use 'set_data_folder(path)'.")
    logger.info("get_fingerprints: db:{} fp_name:{}".format(db_name, fp_name))
    fp_key = get_fp_dictionary_key(db_name, fp_name, pars)
    if fp_key not in _fp_dictionary:
        _fp_dictionary[fp_key] = {}
    fp_dict = _fp_dictionary[fp_key]
    if "fp_file" in fp_dict and os.path.exists(get_full_filename(fp_dict["fp_file"])):
        logger.info("get_fingerprints: fp file found: {}".format(fp_dict["fp_file"]))
        fp_filename = fp_dict["fp_file"]
    else:
        fp_filename = get_fp_filename(db_name, fp_name, pars)
        logger.info("get_fingerprints: Calculating fps")
        # calculate fingerprints
        with auto_open(get_full_filename(fp_filename), "wt") as of:
            print("#    database: {}".format(db_name), file=of)
            print("# fingerprint: {}".format(fp_name), file=of)
            print("# parameters: {}".format(to_key_val_string(pars)), file=of)
            print("# Name    Fingerprint", file=of)
            fp_fct = fingerprints[fp_name]
            count = 0
            bad_count = 0
            mol_suppl = get_mol_suppl()
            for m in mol_suppl:
                if m:
                    fp = fp_fct(m, **pars)
                    name = m.GetProp("_Name") if m.HasProp("_Name") else "mol-{}".format(count + 1)
                    print("{}\t{}".format(name, " ".join(str(x) for x in fp)), file=of)
                else:
                    bad_count += 1
                count += 1
        logger.info("get_fingerprints: fingerprints for {} molecules generated".format(count - bad_count))
        if bad_count:
            logger.warning(
                "get_fingerprints: Molecules could not be generated for {} entries for db {}".format(bad_count,
                                                                                                     db_name))
        fp_dict["fp_file"] = fp_filename
        pickle_fp_dictionary()
    return fp_filename


def cb_mol_suppl_from_file(filename, smilesColumn=0, nameColumn=1, titleLine=False, delimiter=' '):
    if os.path.splitext(filename)[1].lower() == ".sdf":
        return lambda: Chem.SDMolSupplier(filename)
    else:
        return lambda: Chem.SmilesMolSupplier(filename, delimiter=delimiter, smilesColumn=smilesColumn,
                                              nameColumn=nameColumn,
                                              titleLine=titleLine)


def cb_fp_iterator_from_file(filename):
    def generator():
        with auto_open(filename) as inf:
            for line in inf:
                if line.startswith("#"):
                    continue
                id, fp = line.rstrip("\r\n").split("\t")
                fp = fp.split()
                fp = list(map(int, fp))
                yield fp

    return generator


def get_feature_statistics(db_name, fp_name, pars={}, get_mol_suppl=None, limit=2048):
    if not _initialized:
        raise Exception("Data folder not set. Use 'set_data_folder(path)'.")
    logger.info("get_pairwise_stats: db:{} fp_name:{} limit:{}".format(db_name, fp_name, limit))
    fp_key = get_fp_dictionary_key(db_name, fp_name, pars)
    if fp_key not in _fp_dictionary:
        _fp_dictionary[fp_key] = {}
    fp_dict = _fp_dictionary[fp_key]
    stat_key = "pairwise-{}".format(limit)
    if stat_key in fp_dict and os.path.exists(get_full_filename(fp_dict[stat_key])):
        logger.info("get_pairwise_stats: unpickle stats from '{}'".format(fp_dict[stat_key]))
        with auto_open(get_full_filename(fp_dict[stat_key]), "rb") as pf:
            return PairwiseStats.unpickle(pf)
    else:
        if isinstance(get_mol_suppl, str):
            get_mol_suppl = cb_mol_suppl_from_file(get_mol_suppl)
        fp_filename = get_fingerprints(db_name, fp_name, pars, get_mol_suppl)
        get_fp_suppl = cb_fp_iterator_from_file(get_full_filename(fp_filename))
        logger.info("get_pairwise_stats: Calculating pairwise stats")
        pw_stats = PairwiseStats.from_fingerprints(get_fp_suppl, limit=limit)
        pw_stat_filename = get_stats_filename(db_name, fp_name, pars, limit)
        logger.info("get_pairwise_stats: pickling stats to '{}'".format(pw_stat_filename))
        with auto_open(get_full_filename(pw_stat_filename), "wb") as pf:
            pw_stats.pickle(pf)
        fp_dict[stat_key] = pw_stat_filename
        pickle_fp_dictionary()
        return pw_stats


def set_data_folder(path):
    global _base_folder
    global _fp_dictionary_pickle
    global _fp_dictionary
    global _initialized
    _base_folder = path
    _fp_dictionary_pickle = os.path.join(_base_folder, "fp_dictionary.pickle")
    _fp_dictionary = {}
    if os.path.exists(_fp_dictionary_pickle):
        with open(_fp_dictionary_pickle, "rb") as pf:
            _fp_dictionary = pickle\
                .load(pf)
    else:
        pickle_fp_dictionary()
    _initialized = True

fingerprints = {"rdkit": rdkit_fingerprint,
                "maccs": maccs_keys,
                "atom_pairs": atom_pairs,
                "torsions": torsions,
                "morgan": morgan,
                "hashed_atom_pairs": hashed_atom_pairs,
                "hashed_torsions": hashed_torsions,
                "hashed_morgan": hashed_morgan,
                "avalon": avalon,
                }


logger = logging.getLogger(__name__)

pp = pprint.PrettyPrinter(indent=4, depth=6)

_base_folder = None
_fp_dictionary_pickle = None
_fp_dictionary = None
_initialized = False

logger.debug("_fp_dictionary: {}".format(pp.pformat(_fp_dictionary)))

if __name__ == "__main__":
    logging.basicConfig()
    root_logger=logging.getLogger()
    root_logger.setLevel(logging.INFO)

    import sys
    if len(sys.argv)!=4:
        print("Usage: python {} data-folder dbname smiles-file ".format(sys.argv[0]))
        sys.exit(1)
    set_data_folder(sys.argv[1])
    fp_names = ["atom_pairs", "avalon", "maccs", "morgan", "morgan", "rdkit", "torsions",
                "hashed_atom_pairs", "hashed_morgan", "hashed_morgan", "hashed_torsions"]
    fp_pars = [{} for _ in range(11)]
    fp_pars[3] = fp_pars[8] = {"radius": 1}
    fp_pars[4] = fp_pars[9] = {"radius": 2}

    db_name = sys.argv[2]
    filename = sys.argv[3]

    for fp_name,fp_par in zip(fp_names,fp_pars):
        stats = get_feature_statistics(db_name, fp_name, fp_par, filename)
