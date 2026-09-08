import os
import re
import csv
import json
import time
import hashlib
import requests
from urllib.parse import urlparse
import sys


# ============================================================
# WINDOWS UTF-8 SUPPORT
# ============================================================

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


# ============================================================
# CONFIGURATION
# ============================================================

PAGE_SIZE = 5
REQUEST_DELAY = 1

INPUT_FILE = "product_urls.txt"

OUTPUT_DIR = "output_v4"

CSV_FILE = os.path.join(
    OUTPUT_DIR,
    "reviews.csv"
)

PRODUCT_MEMORY_FILE = os.path.join(
    OUTPUT_DIR,
    "products.json"
)

REVIEW_MEMORY_FILE = os.path.join(
    OUTPUT_DIR,
    "reviews.json"
)

PRODUCT_IMAGE_DIR = os.path.join(
    OUTPUT_DIR,
    "images",
    "products"
)

REVIEW_IMAGE_DIR = os.path.join(
    OUTPUT_DIR,
    "images",
    "reviews"
)


# ============================================================
# CSV COLUMNS
# ============================================================

CSV_COLUMNS = [
    "review_id",
    "product_id",
    "marketplace",
    "product_title",
    "product_url",
    "product_image_url",
    "product_image_path",
    "rating",
    "review_text",
    "review_image_urls",
    "review_image_paths",
    "verified_purchase",
    "annotator_id",
    "final_label"
]


# ============================================================
# CREATE DIRECTORIES
# ============================================================

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)

os.makedirs(
    PRODUCT_IMAGE_DIR,
    exist_ok=True
)

os.makedirs(
    REVIEW_IMAGE_DIR,
    exist_ok=True
)


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.daraz.com.bd/"
})


# ============================================================
# LOAD JSON
# ============================================================

def load_json(file_path, default):

    if not os.path.exists(file_path):
        return default

    try:

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception as e:

        print(
            f"WARNING: Could not load "
            f"{file_path}: {e}"
        )

        return default


# ============================================================
# SAVE JSON
# ============================================================

def save_json(file_path, data):

    with open(
        file_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# LOAD EXISTING CSV
# ============================================================

def load_existing_csv():

    if not os.path.exists(CSV_FILE):
        return []

    rows = []

    try:

        with open(
            CSV_FILE,
            "r",
            newline="",
            encoding="utf-8-sig"
        ) as f:

            reader = csv.DictReader(f)

            for row in reader:
                rows.append(row)

    except Exception as e:

        print(
            f"WARNING: Could not read existing CSV: "
            f"{e}"
        )

    return rows


# ============================================================
# SAVE CSV
# ============================================================

def save_csv(rows):

    with open(
        CSV_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=CSV_COLUMNS
        )

        writer.writeheader()

        writer.writerows(rows)


# ============================================================
# EXTRACT DARAZ ITEM ID
# ============================================================

def extract_item_id(product_url):

    match = re.search(
        r"-i(\d+)-s\d+\.html",
        product_url
    )

    if match:
        return match.group(1)

    match = re.search(
        r"-i(\d+)",
        product_url
    )

    if match:
        return match.group(1)

    return None


# ============================================================
# BENGALI DETECTION
# ============================================================

def contains_bengali(text):

    if not text:
        return False

    return bool(
        re.search(
            r"[\u0980-\u09FF]",
            text
        )
    )


# ============================================================
# CLEAN REVIEW TEXT
# ============================================================

def clean_review_text(text):

    if not text:
        return ""

    text = str(text)

    text = re.sub(
        r"[\r\n\t]+",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# DOWNLOAD IMAGE
# ============================================================

def download_image(url, save_path):

    try:

        response = session.get(
            url,
            timeout=30
        )

        response.raise_for_status()

        with open(
            save_path,
            "wb"
        ) as f:

            f.write(
                response.content
            )

        return True

    except Exception as e:

        print(
            f"      Image download failed: {e}"
        )

        return False


# ============================================================
# IMAGE EXTENSION
# ============================================================

def get_image_extension(url):

    try:

        parsed_path = urlparse(
            url
        ).path

        extension = os.path.splitext(
            parsed_path
        )[1].lower()

    except Exception:

        extension = ""

    if extension not in [
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    ]:

        extension = ".jpg"

    return extension


# ============================================================
# FALLBACK REVIEW KEY
# ============================================================

def create_fallback_review_key(
    item_id,
    review
):

    review_text = clean_review_text(
        review.get("reviewContent") or ""
    )

    review_time = str(
        review.get("reviewTime") or ""
    )

    rating = str(
        review.get("rating") or ""
    )

    raw_key = (
        f"{item_id}|"
        f"{review_text}|"
        f"{review_time}|"
        f"{rating}"
    )

    return hashlib.sha256(
        raw_key.encode("utf-8")
    ).hexdigest()


# ============================================================
# REVIEW KEY
# ============================================================

def get_review_key(
    item_id,
    review
):

    review_rate_id = review.get(
        "reviewRateId"
    )

    if review_rate_id:

        return (
            f"{item_id}:"
            f"{review_rate_id}"
        )

    return (
        f"{item_id}:"
        f"{create_fallback_review_key(
            item_id,
            review
        )}"
    )


# ============================================================
# GET REVIEW PAGE
# ============================================================

def get_review_page(
    item_id,
    page_no
):

    api_url = (
        "https://my.daraz.com.bd/"
        "pdp/review/getReviewList"
    )

    params = {
        "itemId": item_id,
        "pageSize": PAGE_SIZE,
        "filter": 0,
        "sort": 0,
        "pageNo": page_no
    }

    try:

        response = session.get(
            api_url,
            params=params,
            timeout=30
        )

        print(
            f"Page {page_no}: "
            f"HTTP {response.status_code}"
        )

        response.raise_for_status()

        return response.json()

    except Exception as e:

        print(
            f"ERROR getting page "
            f"{page_no}: {e}"
        )

        return None


# ============================================================
# NEXT PRODUCT NUMBER
# ============================================================

def get_next_product_number(
    product_memory
):

    numbers = []

    for data in product_memory.values():

        if not isinstance(data, dict):
            continue

        product_id = data.get(
            "product_id",
            ""
        )

        match = re.match(
            r"PD(\d+)",
            str(product_id)
        )

        if match:

            numbers.append(
                int(match.group(1))
            )

    if not numbers:
        return 1

    return max(numbers) + 1


# ============================================================
# NEXT REVIEW NUMBER
# ============================================================

def get_next_review_number(
    review_memory
):

    numbers = []

    for data in review_memory.values():

        if not isinstance(data, dict):
            continue

        review_id = data.get(
            "review_id",
            ""
        )

        match = re.match(
            r"RV(\d+)",
            str(review_id)
        )

        if match:

            numbers.append(
                int(match.group(1))
            )

    if not numbers:
        return 1

    return max(numbers) + 1


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 65)

    print(
        "DARAZ BENGALI ELECTRONICS "
        "INCREMENTAL SCRAPER V4"
    )

    print("=" * 65)


    # ========================================================
    # READ PRODUCT URLS
    # ========================================================

    if not os.path.exists(
        INPUT_FILE
    ):

        print(
            f"\nERROR: {INPUT_FILE} not found."
        )

        print(
            "\nCreate product_urls.txt "
            "and add one Daraz product URL "
            "per line."
        )

        return


    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        product_urls = [
            line.strip()
            for line in f
            if line.strip()
        ]


    if not product_urls:

        print(
            "\nNo product URLs found."
        )

        return


    # ========================================================
    # LOAD EXISTING DATA
    # ========================================================

    product_memory = load_json(
        PRODUCT_MEMORY_FILE,
        {}
    )

    review_memory = load_json(
        REVIEW_MEMORY_FILE,
        {}
    )

    existing_rows = load_existing_csv()


    # ========================================================
    # ID COUNTERS
    # ========================================================

    next_product_number = (
        get_next_product_number(
            product_memory
        )
    )

    next_review_number = (
        get_next_review_number(
            review_memory
        )
    )


    # ========================================================
    # STATISTICS
    # ========================================================

    products_already_known = 0
    products_new = 0

    reviews_seen = 0
    reviews_new = 0
    reviews_already_known = 0

    empty_removed = 0
    non_bengali_removed = 0

    reviews_with_images = 0
    reviews_without_images = 0


    print(
        f"\nURLs supplied this run : "
        f"{len(product_urls)}"
    )

    print(
        f"Known products        : "
        f"{len(product_memory)}"
    )

    print(
        f"Known reviews         : "
        f"{len(review_memory)}"
    )


    # ========================================================
    # PROCESS PRODUCTS
    # ========================================================

    for product_url in product_urls:

        print("\n")
        print("=" * 65)

        print(
            "PROCESSING PRODUCT"
        )

        print("=" * 65)

        print(
            f"URL: {product_url}"
        )


        # ----------------------------------------------------
        # EXTRACT ITEM ID
        # ----------------------------------------------------

        item_id = extract_item_id(
            product_url
        )

        if not item_id:

            print(
                "ERROR: Could not extract "
                "Daraz item ID."
            )

            continue


        print(
            f"Daraz item ID: {item_id}"
        )


        # ====================================================
        # CHECK PRODUCT MEMORY
        # ====================================================

        if item_id in product_memory:

            product_info = product_memory[
                item_id
            ]

            product_id = product_info[
                "product_id"
            ]

            products_already_known += 1

            print(
                f"\nEXISTING PRODUCT → "
                f"{product_id}"
            )

            print(
                "Checking for new reviews..."
            )

        else:

            product_id = (
                f"PD{next_product_number:02d}"
            )

            next_product_number += 1

            product_info = {
                "product_id":
                    product_id,

                "product_title":
                    "",

                "product_url":
                    product_url,

                "product_image_url":
                    "",

                "product_image_path":
                    ""
            }

            product_memory[
                item_id
            ] = product_info

            products_new += 1

            print(
                f"\nNEW PRODUCT → "
                f"{product_id}"
            )


        # ====================================================
        # GET FIRST REVIEW PAGE
        # ====================================================

        first_page = get_review_page(
            item_id,
            1
        )

        if not first_page:

            print(
                "Could not retrieve "
                "first page."
            )

            continue


        model = first_page.get(
            "model",
            {}
        )

        first_items = (
            model.get("items")
            or []
        )

        paging = (
            model.get("paging")
            or {}
        )

        total_pages = paging.get(
            "totalPages",
            1
        )

        total_items = paging.get(
            "totalItems",
            len(first_items)
        )


        print(
            f"API reported reviews: "
            f"{total_items}"
        )

        print(
            f"Total pages: "
            f"{total_pages}"
        )


        # ====================================================
        # UPDATE PRODUCT INFORMATION
        # ====================================================

        if first_items:

            first_review = first_items[0]

            api_title = (
                first_review.get(
                    "itemTitle"
                )
                or ""
            )

            api_image_url = (
                first_review.get(
                    "itemPic"
                )
                or ""
            )

            api_product_url = (
                first_review.get(
                    "itemUrl"
                )
                or product_url
            )


            if api_title:

                product_info[
                    "product_title"
                ] = api_title


            if api_image_url:

                product_info[
                    "product_image_url"
                ] = api_image_url


            if api_product_url:

                product_info[
                    "product_url"
                ] = api_product_url


        # ====================================================
        # PRODUCT IMAGE
        # ====================================================

        product_image_url = product_info.get(
            "product_image_url",
            ""
        )

        product_image_path = product_info.get(
            "product_image_path",
            ""
        )


        if product_image_url:

            extension = (
                get_image_extension(
                    product_image_url
                )
            )

            product_filename = (
                f"{product_id}"
                f"{extension}"
            )

            local_product_path = os.path.join(
                PRODUCT_IMAGE_DIR,
                product_filename
            )


            if os.path.exists(
                local_product_path
            ):

                product_image_path = (
                    local_product_path
                )

                print(
                    "Product image already exists."
                )

            else:

                print(
                    "Downloading product image..."
                )

                success = download_image(
                    product_image_url,
                    local_product_path
                )

                if success:

                    product_image_path = (
                        local_product_path
                    )

                    print(
                        f"Product image saved: "
                        f"{local_product_path}"
                    )


        product_info[
            "product_image_path"
        ] = product_image_path


        # ====================================================
        # SAVE PRODUCT MEMORY IMMEDIATELY
        # ====================================================

        product_memory[
            item_id
        ] = product_info

        save_json(
            PRODUCT_MEMORY_FILE,
            product_memory
        )


        # ====================================================
        # PROCESS ALL REVIEW PAGES
        # ====================================================

        for page_no in range(
            1,
            total_pages + 1
        ):

            print("\n" + "-" * 65)

            print(
                f"PROCESSING PAGE "
                f"{page_no}/{total_pages}"
            )

            print("-" * 65)


            if page_no == 1:

                page_data = first_page

            else:

                time.sleep(
                    REQUEST_DELAY
                )

                page_data = get_review_page(
                    item_id,
                    page_no
                )


            if not page_data:

                print(
                    "Skipping this page."
                )

                continue


            page_model = page_data.get(
                "model",
                {}
            )

            reviews = (
                page_model.get("items")
                or []
            )


            print(
                f"Reviews on page: "
                f"{len(reviews)}"
            )


            # =================================================
            # PROCESS EACH REVIEW
            # =================================================

            for review in reviews:

                reviews_seen += 1


                # ------------------------------------------------
                # UNIQUE REVIEW KEY
                # ------------------------------------------------

                review_key = get_review_key(
                    item_id,
                    review
                )


                # =================================================
                # CHECK REVIEW MEMORY
                # =================================================

                if review_key in review_memory:

                    reviews_already_known += 1

                    print(
                        "\n[SKIPPED - "
                        "ALREADY COLLECTED]"
                    )

                    continue


                # =================================================
                # REVIEW TEXT
                # =================================================

                review_text = (
                    review.get(
                        "reviewContent"
                    )
                    or ""
                )

                review_text = (
                    clean_review_text(
                        review_text
                    )
                )


                # =================================================
                # EMPTY REVIEW
                # =================================================

                if not review_text:

                    empty_removed += 1

                    print(
                        "\n[REMOVED - "
                        "EMPTY REVIEW]"
                    )

                    review_memory[
                        review_key
                    ] = {
                        "status":
                            "empty_removed"
                    }

                    save_json(
                        REVIEW_MEMORY_FILE,
                        review_memory
                    )

                    continue


                # =================================================
                # BENGALI FILTER
                # =================================================

                if not contains_bengali(
                    review_text
                ):

                    non_bengali_removed += 1

                    print(
                        "\n[REMOVED - "
                        "NON-BENGALI]"
                    )

                    print(
                        f"Text: "
                        f"{review_text}"
                    )

                    review_memory[
                        review_key
                    ] = {
                        "status":
                            "non_bengali_removed"
                    }

                    save_json(
                        REVIEW_MEMORY_FILE,
                        review_memory
                    )

                    continue


                # =================================================
                # NEW BENGALI REVIEW
                # =================================================

                review_id = (
                    f"RV{next_review_number:02d}"
                )

                next_review_number += 1

                reviews_new += 1


                # =================================================
                # BASIC REVIEW DATA
                # =================================================

                rating = review.get(
                    "rating",
                    ""
                )

                verified_purchase = (
                    review.get(
                        "isPurchased",
                        ""
                    )
                )


                # =================================================
                # REVIEW IMAGES
                # =================================================

                images = (
                    review.get(
                        "images"
                    )
                    or []
                )


                review_image_urls = []

                review_image_paths = []


                if images:

                    reviews_with_images += 1

                else:

                    reviews_without_images += 1


                review_folder = os.path.join(
                    REVIEW_IMAGE_DIR,
                    review_id
                )


                if images:

                    os.makedirs(
                        review_folder,
                        exist_ok=True
                    )


                # =================================================
                # DOWNLOAD REVIEW IMAGES
                # =================================================

                for image_index, image in enumerate(
                    images,
                    start=1
                ):

                    if not image:
                        continue


                    image_url = (
                        image.get(
                            "url"
                        )
                        or ""
                    )


                    if not image_url:
                        continue


                    review_image_urls.append(
                        image_url
                    )


                    extension = (
                        get_image_extension(
                            image_url
                        )
                    )


                    image_filename = (
                        f"img_"
                        f"{image_index:02d}"
                        f"{extension}"
                    )


                    local_image_path = os.path.join(
                        review_folder,
                        image_filename
                    )


                    print(
                        f"      Downloading "
                        f"review image "
                        f"{image_index}..."
                    )


                    if os.path.exists(
                        local_image_path
                    ):

                        print(
                            "      Image already exists."
                        )

                        review_image_paths.append(
                            local_image_path
                        )

                        continue


                    success = download_image(
                        image_url,
                        local_image_path
                    )


                    if success:

                        print(
                            f"      Saved: "
                            f"{local_image_path}"
                        )

                        review_image_paths.append(
                            local_image_path
                        )


                # =================================================
                # CREATE CSV ROW
                # =================================================

                row = {

                    "review_id":
                        review_id,

                    "product_id":
                        product_id,

                    "marketplace":
                        "Daraz",

                    "product_title":
                        product_info.get(
                            "product_title",
                            ""
                        ),

                    "product_url":
                        product_info.get(
                            "product_url",
                            product_url
                        ),

                    "product_image_url":
                        product_info.get(
                            "product_image_url",
                            ""
                        ),

                    "product_image_path":
                        product_info.get(
                            "product_image_path",
                            ""
                        ),

                    "rating":
                        rating,

                    "review_text":
                        review_text,

                    "review_image_urls":
                        " | ".join(
                            review_image_urls
                        ),

                    "review_image_paths":
                        " | ".join(
                            review_image_paths
                        ),

                    "verified_purchase":
                        verified_purchase,

                    "annotator_id":
                        "",

                    "final_label":
                        ""
                }


                # =================================================
                # ADD TO DATASET
                # =================================================

                existing_rows.append(
                    row
                )


                # =================================================
                # REMEMBER REVIEW
                # =================================================

                review_memory[
                    review_key
                ] = {

                    "review_id":
                        review_id,

                    "product_id":
                        product_id
                }


                # =================================================
                # PRINT
                # =================================================

                print(
                    "\n[NEW BENGALI REVIEW]"
                )

                print(
                    f"Review ID : "
                    f"{review_id}"
                )

                print(
                    f"Product ID: "
                    f"{product_id}"
                )

                print(
                    f"Rating    : "
                    f"{rating}"
                )

                print(
                    f"Purchased : "
                    f"{verified_purchase}"
                )

                print(
                    f"Images    : "
                    f"{len(images)}"
                )

                print(
                    f"Text      : "
                    f"{review_text}"
                )


                # ------------------------------------------------
                # SAVE REVIEW MEMORY AFTER EACH REVIEW
                # ------------------------------------------------

                save_json(
                    REVIEW_MEMORY_FILE,
                    review_memory
                )


        # ========================================================
        # SAVE AFTER EACH PRODUCT
        # ========================================================

        save_json(
            PRODUCT_MEMORY_FILE,
            product_memory
        )

        save_json(
            REVIEW_MEMORY_FILE,
            review_memory
        )

        save_csv(
            existing_rows
        )


        print(
            f"\nFinished product: "
            f"{product_id}"
        )


    # ========================================================
    # FINAL SAVE
    # ========================================================

    save_json(
        PRODUCT_MEMORY_FILE,
        product_memory
    )

    save_json(
        REVIEW_MEMORY_FILE,
        review_memory
    )

    save_csv(
        existing_rows
    )


    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("\n")
    print("=" * 65)

    print(
        "V4 INCREMENTAL SCRAPING COMPLETE"
    )

    print("=" * 65)


    print(
        f"\nProducts supplied this run : "
        f"{len(product_urls)}"
    )

    print(
        f"Existing products          : "
        f"{products_already_known}"
    )

    print(
        f"New products               : "
        f"{products_new}"
    )

    print(
        f"\nReviews seen this run      : "
        f"{reviews_seen}"
    )

    print(
        f"New Bengali reviews        : "
        f"{reviews_new}"
    )

    print(
        f"Already collected reviews  : "
        f"{reviews_already_known}"
    )

    print(
        f"Empty reviews removed      : "
        f"{empty_removed}"
    )

    print(
        f"Non-Bengali removed        : "
        f"{non_bengali_removed}"
    )

    print(
        f"\nNew reviews with images    : "
        f"{reviews_with_images}"
    )

    print(
        f"New reviews without images : "
        f"{reviews_without_images}"
    )

    print(
        f"\nTOTAL DATASET ROWS         : "
        f"{len(existing_rows)}"
    )

    print(
        f"\nCSV: "
        f"{CSV_FILE}"
    )

    print(
        f"Product memory: "
        f"{PRODUCT_MEMORY_FILE}"
    )

    print(
        f"Review memory: "
        f"{REVIEW_MEMORY_FILE}"
    )

    print(
        "\nDuplicate review TEXT was NOT removed."
    )

    print(
        "REAL/FAKE labels were NOT assigned."
    )

    print(
        "\nYou can now add another batch of "
        "product URLs and run V4 again."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()