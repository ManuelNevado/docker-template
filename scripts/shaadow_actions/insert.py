import os
import json
import logging
import time
import shadow as shaadow


# Environment variables
CWD = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(CWD, "..", "configs")

# Logger
logging.basicConfig(format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(os.environ["LOGGER_LEVEL"])


def get_traceability(trace_output_obj) -> list:
    """Return a list with all the previous marks"""

    # WITH DIGITAL MARK
    marks = []
    for i in range(0, len(trace_output_obj.pageMark)):
        logger.debug("Page {}:".format(i))
        for k in range(0, len(trace_output_obj.pageMark[i])):
            logger.debug(
                "Mark "
                + trace_output_obj.pageMark[i][k]
                + " with score"
                + str(trace_output_obj.pageExtractionScore[i][k])
            )
            if "-" not in trace_output_obj.pageMark[i][k]:
                marks.append(trace_output_obj.pageMark[i][k])
    marks = list(dict.fromkeys(marks))
    return marks


def print_all_atributes(insert_object):
    print(dir(insert_object))
    # Print all attributes
    print("current_config: %s" % insert_object.current_config)
    print("error: %s" % insert_object.error)
    print("error_mssg: %s" % insert_object.error_mssg)
    print("pageReliability: %s" % insert_object.pageReliability)
    print("pageSpaces: %s" % insert_object.pageSpaces)
    print("pageValidSpaces: %s" % insert_object.pageValidSpaces)
    print("version: %s" % insert_object.version)
    print("documentWarnings: %s" % insert_object.documentWarnings)
    print("pageWarning: %s" % insert_object.pageWarning)


def insert(input_path, output_path, mark, config_file="/config_shaadow.json") -> dict:
    logger.debug("Insert mark...")
    logger.info("Mark file %s with %s", input_path, mark)
    return_info = {
        "originalPages": "",
        "markedPages": "",
        "originalSize": "",
        "markedSize": "",
        "insertTime": "",
        "libVersion": "",
        "trace": [],
        "reliability": [],
        "discardedReliability": [],
    }

    # Config shadow
    sh = shaadow.shadow()
    config_shaadow_path = CONFIG_PATH + config_file
    with open(config_shaadow_path) as f:
        configjson = json.load(f)
    logger.debug("shaadow config: %s", configjson)
    sh.config(json.dumps(configjson))

    # Pdf to binary file
    binary_file = shaadow.utils.read_binary_file(input_path)
    return_info["originalSize"] = len(binary_file)
    logger.debug("Binary file length: %s", str(len(binary_file)))

    # Traceability
    mark_length = 12
    trace_output = sh.trace(binary_file, mark_length)
    marks_trace = get_traceability(trace_output)
    return_info["trace"] = marks_trace

    # Mark document
    start = time.time()

    insert_output = sh.insert(binary_file, mark)

    end = time.time()
    print_all_atributes(insert_output)
    logger.info(
        "Time used to insert Mark in %s pages was %s ms",
        len(insert_output.pageReliability),
        1000 * (end - start),
    )
    return_info["insertTime"] = 1000 * (end - start)
    return_info["originalPages"] = len(insert_output.pageReliability)
    return_info["libVersion"] = insert_output.version

    # Transformar objeto reliability en list
    for e in insert_output.pageReliability:
        return_info["reliability"].append(str(e).replace("reliability.", ""))

    # Count marked pages
    marked_pages = 0
    if insert_output.error == 0:
        # loop pages information
        for i in range(len(insert_output.pageReliability)):
            logger.debug(
                "Page %s : %s", str(i + 1), str(insert_output.pageReliability[i])
            )

        # descartar páginas para el conteo final
        discard_reliability = [
            "reliability.WithoutMark",
            "reliability.WithoutText",
            "reliability.UnsupportedAlphabet",
            "reliability.NotSupported",
        ]
        logger.debug(f"Discard reliability: {str(discard_reliability)}")
        marked_pages = sum(
            map(
                lambda x: str(x) not in discard_reliability,
                insert_output.pageReliability,
            )
        )
        logger.info(
            f"Marked pages: {str(marked_pages)}/{str(len(insert_output.pageReliability))}"
        )
        return_info["discardedReliability"] = discard_reliability

        if marked_pages == 0:
            reliability_str = ", ".join(
                str(e).replace("reliability.", "")
                for e in insert_output.pageReliability
            )
            logger.info(reliability_str)

        return_info["markedPages"] = marked_pages
        return_info["markedSize"] = len(insert_output.markedFile)
        logger.debug("Writing file in %s", output_path)
        shaadow.utils.write_binary_file(insert_output.markedFile, output_path)
    elif insert_output.error == 1:
        logger.error(
            f"Error marking document: [{str(insert_output.error)}, {insert_output.warning}]"
        )
        return {
            "error": True,
            "errorCode": insert_output.error,
            "errorMessage": insert_output.warning,
            "mark": mark,
            "reliability": [],
        }
    else:
        logger.error(
            f"Error marking document: [{str(insert_output.error)}, {insert_output.error_mssg}]"
        )
        return {
            "error": True,
            "errorCode": insert_output.error,
            "errorMessage": insert_output.error_mssg,
            "mark": mark,
            "reliability": [],
        }
    return_info["error"] = False
    return return_info
