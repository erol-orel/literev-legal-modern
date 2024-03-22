import json
import pytest
from etl import DataTranslator


@pytest.fixture
def record_sample():
    return json.loads("""{
        "resume":"Refus de supprimer du dossier de police de la recourante un rapport de renseignements et ses annexes. Déjà condamnée, il n'y avait pas lieu de prendre en compte l'aspect de répression des infractions. Condamnée pour voies de faits : contravention qui ne rentre pas dans le but de prévention des crimes et délits prévu par la LCBVM. Examen de l'ensemble des circonstances (ordonnance pénale et de non-entrée en matière partielle ne figure pas dans les dossiers de police et n'y est pas mentionnée ; condamnation pour une contravention, absence d'antécédents, absence de gravité comme la criminalité organisée ou les crimes et délits contre l'intégrité physique et sexuelle, moins d'un an depuis le rapport de renseignements et la condamnation). Absence d'intérêt à la conservation des documents litigieux. Recours admis et radiation du document ordonnée.",
        "normes":"LPA.65;LPA.69.al1;Cst.10.al2;Cst.13.al2;Cst-GE.21;LCBVM.2;LIPAD.36.al1.leta;LIPAD.35.al2;LCBVM.1.al3;LIPAD.4.alb.ch4;LCBVM.3A.al1;LIPAD.47.al2.leta;LCBVM.3A.al2",
        "proc_year":"2022",
        "parties":"",
        "recours":[
            {
            "index":0,
            "chambre":"4",
            "d_modif":"15.06.2023",
            "date_debut":"21.11.2022",
            "type":"DROIT PUBLIC",
            "nature":"FPUBL",
            "ts_modif":"15/06/23 05:15:20.693054",
            "cle_decis_recours":"34962",
            "no_atf":"8D_9/2022",
            "no_decis":"ATA/1048/2022",
            "no_procedure":"A/1681/2022",
            "cle_action":"1004992222",
            "type_recours":"TF",
            "t_modif":"05:15:20",
            "date_fin":"30.05.2023",
            "oper_modif":"PJCV_USR",
            "cle_fiche":"3143374",
            "etat_action":"O",
            "resultat":null,
            "ts_creat":"25/11/22 05:15:32.348287",
            "oper_creat":"PJCV_USR"
            }
        ],
        "publieinternet":"B",
        "rectification":null,
        "cle_fiche":"3265672",
        "datedecision":"16.05.2023",
        "procedure":"A/3741/2022",
        "decision":"ATA/504/2023",
        "importance":null,
        "n_ext_proc":null,
        "document":"<h1>Lorem ipsum dolor</h1>",
        "nature":"LIPAD",
        "dt_decision":"16.05.2023",
        "coll_nom":"ata",
        "relations":"",
        "source":null,
        "fichierword":"/2023/0005/ATA_000504_2023_A_3741_2022.docx",
        "arretdeprincipe":"false",
        "n_ext_jur_attr":"LIPAD",
        "resultat":"ADMIS",
        "document_text":"Lorem ipsum dolor",
        "descripteurs":"FORME ET CONTENU;OBJET DU LITIGE;LIBERTÉ PERSONNELLE;DONNÉES PERSONNELLES;FICHIER DE DONNÉES;SUPPRESSION(EN GÉNÉRAL)",
        "id":"1685021361"
    }""")

@pytest.fixture
def root_fields_in_french():
    """List of root level document fields in French."""
    return [
        key for key, value in DataTranslator.ROOT_FIELD_MAP.items()
        if key != value # keep only translated words
    ]

@pytest.fixture
def appeal_fields_in_french():
    """List of appeal fields in French."""
    return [
        key for key, value in DataTranslator.APPEAL_FIELD_MAP.items()
        if key != value # keep only translated words
    ]

@pytest.fixture
def translator() -> DataTranslator:
    return DataTranslator()

# --------------Test document translation--------------
def test_translate_document_fields_root_level_should_succeed(record_sample, root_fields_in_french, appeal_fields_in_french, translator):
    translated_doc = translator.translate_document_fields(record_sample)
    for field in root_fields_in_french:
        # assert that french words are not in the document
        # after transalation
        assert field not in translated_doc
    
    appeals = translated_doc["appeals"][0]
    for field in appeal_fields_in_french:
        assert field not in appeals

def test_missing_fields_are_translated_and_set_should_succeed(record_sample, translator):
    # remove apppeal/recours key
    del record_sample["recours"]
    translated_doc = translator.translate_document_fields(record_sample)
    assert "appeals" in translated_doc
    assert translated_doc["appeals"] == []


def test_noise_fields_are_removed_during_translation_should_succeed(record_sample, translator):
    # add query key
    record_sample["query"] = "lalalalala"
    translated_doc = translator.translate_document_fields(record_sample)
    # assert that query key was deleted
    assert "query" not in translated_doc


def test_null_fields_are_set_to_none_should_succeed(record_sample):
    null_fields = [
        "rectification",
        "importance",
        "n_ext_proc",
        "source", 
    ]

    for field in null_fields:
        assert record_sample[field] is None


def test_missing_fields_are_added_and_set_to_none_should_succeed(record_sample, translator):
    missing_fields = [
        "rectification",
        "importance",
        "n_ext_proc",
        "source", 
    ]

    for field in missing_fields:
        del record_sample[field]

    translated_doc = translator.translate_document_fields(record_sample)
    
    for field in missing_fields:
        assert translated_doc[DataTranslator.ROOT_FIELD_MAP[field]] == translated_doc[DataTranslator.ROOT_FIELD_MAP[field]] is None

def test_appeal_null_fields_are_set_to_none_should_succeed(record_sample):
    assert record_sample["recours"][0]["resultat"] is None

def test_appeal_missing_fields_are_translated_and_set_should_succeed(record_sample, translator):
    del record_sample["recours"][0]["resultat"]
    translated_doc = translator.translate_document_fields(record_sample)
    assert translated_doc["appeals"][0]["result"] is None
