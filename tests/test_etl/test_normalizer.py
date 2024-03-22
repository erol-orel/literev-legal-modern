import json
import pytest
from etl import DataNormalizer


@pytest.fixture
def normalizer() -> DataNormalizer:
    return DataNormalizer()

@pytest.fixture
def translated_doc():
    return json.loads("""{
        "summary": "Refus de supprimer du dossier de police de la recourante un rapport de renseignements et ses annexes. D\u00e9j\u00e0 condamn\u00e9e, il n'y avait pas lieu de prendre en compte l'aspect de r\u00e9pression des infractions. Condamn\u00e9e pour voies de faits : contravention qui ne rentre pas dans le but de pr\u00e9vention des crimes et d\u00e9lits pr\u00e9vu par la LCBVM. Examen de l'ensemble des circonstances (ordonnance p\u00e9nale et de non-entr\u00e9e en mati\u00e8re partielle ne figure pas dans les dossiers de police et n'y est pas mentionn\u00e9e ; condamnation pour une contravention, absence d'ant\u00e9c\u00e9dents, absence de gravit\u00e9 comme la criminalit\u00e9 organis\u00e9e ou les crimes et d\u00e9lits contre l'int\u00e9grit\u00e9 physique et sexuelle, moins d'un an depuis le rapport de renseignements et la condamnation). Absence d'int\u00e9r\u00eat \u00e0 la conservation des documents litigieux. Recours admis et radiation du document ordonn\u00e9e.",
        "standards": "LPA.65;LPA.69.al1;Cst.10.al2;Cst.13.al2;Cst-GE.21;LCBVM.2;LIPAD.36.al1.leta;LIPAD.35.al2;LCBVM.1.al3;LIPAD.4.alb.ch4;LCBVM.3A.al1;LIPAD.47.al2.leta;LCBVM.3A.al2",
        "procedure_year": "2022",
        "parties_involved": "",
        "appeals": [
            {
            "index": 0,
            "end_date": "30.05.2023",
            "appeal_type": "TF",
            "modification_time": "05:15:20",
            "modified_by": "PJCV_USR",
            "action_status": "O",
            "record_key": "3143374",
            "result": null,
            "created_by": "PJCV_USR",
            "creation_timestamp": "25/11/22 05:15:32.348287",
            "chamber": "4",
            "modification_date": "15.06.2023",
            "case_type": "DROIT PUBLIC",
            "start_date": "21.11.2022",
            "decision_appeal_key": "34962",
            "decision_number": "ATA/1048/2022",
            "atf_number": "8D_9/2022",
            "modification_timestamp": "15/06/23 05:15:20.693054",
            "case_nature": "FPUBL",
            "action_key": "1004992222",
            "procedure_number": "A/1681/2022"
            }
        ],
        "published_internet": "B",
        "correction": null,
        "record_key": "3265672",
        "decision_date": "16.05.2023",
        "procedure_type": "A/3741/2022",
        "decision_type": "ATA/504/2023",
        "importance": null,
        "external_procedure_number": null,
        "document": "<h1>Lorem ipsum dolor</h1>",
        "nature": "LIPAD",
        "collector_name": "ata",
        "relations": "",
        "source": null,
        "word_file": "/2023/0005/ATA_000504_2023_A_3741_2022.docx",
        "stopped_from_begin": "false",
        "external_jurisdiction_attribute": "LIPAD",
        "result": "ADMIS",
        "document_text": "Lorem ipsum dolor",
        "descriptors": "FORME ET CONTENU;OBJET DU LITIGE;LIBERT\u00c9 PERSONNELLE;DONN\u00c9ES PERSONNELLES;FICHIER DE DONN\u00c9ES;SUPPRESSION(EN G\u00c9N\u00c9RAL)",
        "id": "1685021361"
        }""")


# --------------Test DataNormalizer--------------

def test_normalize_document_should_succeed(normalizer, translated_doc):
    DOC_DECISION_DATE = "decision_date"
    APPEAL_START_DATE = "start_date"
    APPEAL_END_DATE = "end_date"
    APPEAL_MODIFICATION_DATE = "modification_date"
    APPEAL_CREATION_TIMESTAMP = "creation_timestamp"
    APPEAL_MODIFICATION_TIMESTAMP = "modification_timestamp"

    normalized_doc = normalizer.normalize_document(translated_doc)
    normalized_appeal = normalized_doc["appeals"][0]

    # document
    assert normalized_doc[DOC_DECISION_DATE] == "2023-05-16"

    # appeal 
    assert normalized_appeal[APPEAL_START_DATE] == "2022-11-21"
    assert normalized_appeal[APPEAL_END_DATE] == "2023-05-30"
    assert normalized_appeal[APPEAL_MODIFICATION_DATE] == "2023-06-15" 
    assert normalized_appeal[APPEAL_CREATION_TIMESTAMP] == "2022-11-25 05:15:32.348287"
    assert normalized_appeal[APPEAL_MODIFICATION_TIMESTAMP] == "2023-06-15 05:15:20.693054"

def test_normalize_date_should_succeed(normalizer):
    raw_date = "27.11.2022"
    expected_date = "2022-11-27"
    assert normalizer._normalize_date(raw_date) == expected_date

def test_normalize_date_timestamp_should_succeed(normalizer):
    raw_date_timestamp = "27/11/22 05:15:25.055478"
    expected_date_timestamp = "2022-11-27 05:15:25.055478"
    assert normalizer._normalize_date_timestamp(raw_date_timestamp) == expected_date_timestamp