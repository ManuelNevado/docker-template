import os
import json
import logging
import time
from datetime import datetime
import shadow as shaadow
from collections import Counter
from statistics import mean
from pdf2image import convert_from_path

from functions.upload_to_s3 import upload_to_s3

import torch
from torchvision.transforms import transforms
from torchvision.utils import save_image
from PIL import Image, ImageOps

# Environment variables
CWD = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(CWD, "..", "configs")
READ_INFO = os.path.join(CWD, "..", "templates", "readInfo.json")
no_mark = "NO_USER_MARKS"
# Logger
logging.basicConfig(format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(os.environ["LOGGER_LEVEL"])


def print_all_attributes(shaadow_var):
    """print all atributes from lib shaadow"""

    print("error: %s" % shaadow_var.error)
    print("error_mssg: %s" % shaadow_var.error_mssg)
    print("pageExtractionScore: %s" % shaadow_var.pageExtractionScore)
    print("current_config: %s" % shaadow_var.current_config)
    print("isPageSupported: %s" % shaadow_var.isPageSupported)
    print("pageSpaces: %s" % shaadow_var.pageSpaces)
    print("pageValidSpaces: %s" % shaadow_var.pageValidSpaces)
    print("version: %s" % shaadow_var.version)
    print("pageWarning: %s" % shaadow_var.pageWarning)
    print("documentWarning: %s" % shaadow_var.documentWarnings)
    print("digitalMark: %s" % shaadow_var.digitalMark)


def most_common_mark(mark_list) -> str:
    """Extract within a list of marks the most common without the '-' marks."""
    mark_counter = Counter(mark_list)
    logger.debug("Counter: %s", mark_counter)

    counter_keys = mark_counter.keys()
    logger.debug("Keys: %s", counter_keys)
    for elem in list(counter_keys):
        if "-" in elem:
            del mark_counter[elem]
            logger.debug("Delete key: %s", elem)
        elif not elem:
            del mark_counter[elem]
            logger.debug("Delete key: %s", elem)
        else:
            logger.debug("Key: %s", elem)
    logger.info('Counter with deletion of keys with "-": %s', mark_counter)

    try:
        most_common_mark = mark_counter.most_common(1)
        logger.debug("Most common mark: %s", most_common_mark)
        return_mark = most_common_mark[0][0]
    except:
        logger.error("#shaadow didn't find your user marks in the file")
        return_mark = "NO_USER_MARKS"
    return return_mark


def reescalado_inteligente(
    input_path: str, out_ia: str, resize_param: bool = False, patch_arg: int = 256
):
    # input_path: path of the input image
    # out_ia: path where the otput iamge will be written (expected to be deprecated, for resource managing, it is not optimal to save more files)
    # resize_parm: variable for resizing the image only if it's small enough
    #              (samller than 1000 in any of its coordinates due to not having that resolution in trainning dataset)

    generador = torch.jit.load("shaadow_actions/script_model_1.pt")
    kc, kh, kw = 1, patch_arg, patch_arg  # kernel size
    dc, dh, dw = 1, patch_arg, patch_arg  # stride

    # Load image
    image = ImageOps.grayscale(Image.open(input_path))
    # The width and height recalculation is to not loosing pixels in the patchification
    # (n//patch_arg) returns the bottom of the division and adding 1 to get the next multiplier of the patch size
    # multiplying it to patch_arg again give us the next resolution who is a multiplier of the patch_size
    # EXAMPLE: patch_arg = 256, (1000, 1000) -> (1024,1024)
    width = (image.size[0] // patch_arg + 1) * patch_arg
    height = (image.size[1] // patch_arg + 1) * patch_arg

    if resize_param:
        # This param is orquestated
        width *= 2
        height *= 2

    transform = transforms.Compose(
        [transforms.ToTensor(), transforms.Resize((height, width))]
    )
    image = transform(image)
    print(f"Original shape: {image.shape}")

    # Unsqueeze image
    image = image.unsqueeze(0)

    # Patchify image
    patches = image.unfold(1, kc, dc).unfold(2, kh, dh).unfold(3, kw, dw)
    unfold_shape = patches.size()
    patches = patches.contiguous().view(patches.size(0), -1, kc, kh, kw)

    for i in range(patches.shape[1]):
        # print(f"Processing patch: {i}")
        patch = patches[0, i, :, :, :]
        transform_patch = generador(patch.unsqueeze(0)).squeeze(0).detach()
        patches[0, i, :, :, :] = transform_patch

    print(f"Shape of returned is: {patches.shape}")
    patches_orig = patches.view(unfold_shape)
    output_c = unfold_shape[1] * unfold_shape[4]
    output_h = unfold_shape[2] * unfold_shape[5]
    output_w = unfold_shape[3] * unfold_shape[6]
    patches_orig = patches_orig.permute(0, 1, 4, 2, 5, 3, 6).contiguous()
    patches_orig = patches_orig.view(1, output_c, output_h, output_w)
    save_image(patches_orig, out_ia)


def extract(
    context, input_path, config_file="/config_shaadow.json", denoiser=False
) -> dict:

    logger.debug("Handling READ mark")
    logger.info("Read file '%s'", input_path)
    # print("DENOISER: ", denoiser)

    with open(READ_INFO, "r") as f:
        return_info = json.load(f)

    # SHADOW CONFIG
    sh = shaadow.shadow()
    config_shaadow_path = CONFIG_PATH + config_file
    with open(config_shaadow_path) as f:
        configjson = json.load(f)
    logger.debug("configjson: %s", configjson)
    sh.config(json.dumps(configjson))

    # READ BINARY FILE
    binary_file = shaadow.utils.read_binary_file(input_path)
    logger.info("Binary file length: %s", str(len(binary_file)))

    # INICIALIZACION VARIABLES
    modes = ["DEFAULT", "SCREEN_PHOTO", "SCREENSHOT", "IA"]
    return_info["shadow_default"] = False
    return_info["shadow_screenphoto"] = False
    return_info["shadow_screenshot"] = False
    return_info["shaadow_ai_interpolation"] = False
    return_info["extraction_success"] = False
    return_mark = "NO_USER_MARKS"
    i = 0
    # BUCLE EXTRACCION DE MARCA
    start = time.time()
    while return_mark == no_mark and i < 4:

        # DEFAULT
        if modes[i] == "DEFAULT":
            extract_default = sh.extract(binary_file, 12)

            extract_output = extract_default

            return_mark = most_common_mark(extract_output.pageMark)
            return_info["shadow_default"] = True

        # SCREEN_PHOTO
        elif modes[i] == "SCREEN_PHOTO":
            extract_output = sh.extract_expert(
                binary_file, 12, processingMode="SCREEN_PHOTO"
            )
            return_mark = most_common_mark(extract_output.pageMark)
            return_info["shadow_screenphoto"] = True

        # SCREENSHOT
        elif modes[i] == "SCREENSHOT":

            extract_output = sh.extract_expert(
                binary_file, 12, processingMode="SCREENSHOT"
            )

            return_mark = most_common_mark(extract_output.pageMark)
            return_info["shadow_screenshot"] = True

        # IA
        elif modes[i] == "IA":
            out_ia = "/tmp/reescalado_ia.jpg"
            extensions = ["jpg", "jpeg", "png", "JPG", "JPEG", "PNG"]

            if input_path.split(".")[-1] == "pdf":
                pages_types = extract_default.pageType
                max_valid_spaces = -1
                index = -1
                for page_index in range(len(pages_types)):
                    if str(pages_types[page_index]) == "pageType.raster":
                        if (
                            extract_output.pageValidSpaces[page_index]
                            > max_valid_spaces
                        ):
                            max_valid_spaces = extract_output.pageValidSpaces[
                                page_index
                            ]
                            index = page_index
                # control any rasters
                if index != -1:
                    raster_path = "/tmp/raster_pdf.jpg"
                    images = convert_from_path(input_path, size=(None, 900))
                    images[index].save(raster_path)
                    input_path = raster_path
                    print(images[index].size)

                else:
                    logger.debug("No raster pages found in the pdf")

            if input_path.split(".")[-1] in extensions:

                return_info["shaadow_ai_interpolation"] = True

                reescalado_inteligente(input_path, out_ia)
                binary_file = shaadow.utils.read_binary_file(out_ia)

                extract_output = sh.extract_expert(
                    binary_file, 12, processingMode="SCREEN_PHOTO"
                )

                return_mark = most_common_mark(extract_output.pageMark)

                # LAST LAST BULLET
                if return_mark == no_mark:
                    image = ImageOps.grayscale(Image.open(input_path))
                    width = image.size[0]
                    height = image.size[1]
                    if height < 1000 or width < 1000:
                        reescalado_inteligente(input_path, out_ia, resize_param=True)
                        binary_file = shaadow.utils.read_binary_file(out_ia)
                        extract_output = sh.extract_expert(
                            binary_file, 12, processingMode="SCREEN_PHOTO"
                        )
                        return_mark = most_common_mark(extract_output.pageMark)

        # ERROR DE LA LIBRERIA EN LA EXTRACCION
        if extract_output.error == 1:
            logger.warning(
                f"Error extracting mark: [{str(extract_output.error)}, {extract_output.warning}]"
            )
            return {
                "error": True,
                "errorCode": extract_output.error,
                "errorMessage": extract_output.warning,
                "mark": "",
                "reliability": [],
            }
        # OTRO TIPO DE ERROR
        elif extract_output.error != 0:
            logger.error(
                f"Error extracting mark: [{str(extract_output.error)}, {extract_output.error_mssg}]"
            )
            return {
                "error": True,
                "errorCode": extract_output.error,
                "errorMessage": extract_output.error_mssg,
                "mark": "",
                "reliability": [],
            }

        # RECOGER RESULTADOS
        return_info["mark"] = return_mark
        if return_mark != "NO_USER_MARKS":
            return_info["extraction_success"] = True
            end = time.time()
            return_info["extractTime"] = end - start
        # REPORT LAST EXTRACTION
        print_all_attributes(extract_output)
        # NEXT MODE
        i += 1

    if return_info["mark"] == "NO_USER_MARKS":
        end = time.time()
        return_info["extractTime"] = end - start

    for i in range(len(extract_output.pageMark)):
        return_info["extractReliability"]["Page " + str(i + 1)] = str(
            extract_output.pageExtractionScore[i]
        )

        return_info["extractAvgReliability"] = mean(extract_output.pageExtractionScore)
        return_info["extractShaadowVersion"] = extract_output.version
        return_info["extractTotalPages"] = len(extract_output.pageMark)
        return_info["extractPdfname"] = ""
        return_info["extractPageMark"] = extract_output.pageMark
        return_info["error"] = False

        time_log = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_mark = return_info["mark"]
        log_s3_destination_key = f"EXTRACT/{time_log}_{log_mark}_success.log"
        upload_to_s3(
            "../../tmp/shadow.log", os.environ["LOG_BUCKET"], log_s3_destination_key
        )
        return_info["logShadowLib"] = log_s3_destination_key

        logger.debug("return info: %s", return_info)
        return return_info
