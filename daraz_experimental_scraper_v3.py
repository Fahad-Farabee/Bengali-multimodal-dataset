import os
import re
import csv
import time
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

OUTPUT_DIR = "output_v3"
CSV_FILE = os.path.join(OUTPUT_DIR, "reviews.csv")

PRODUCT_IMAGE_DIR = os.path.join(
    OUTPUT_DIR, "images", "products"
)

REVIEW_IMAGE_DIR = os.path.join(
    OUTPUT_DIR, "images", "reviews"
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

os.makedirs(PRODUCT_IMAGE_DIR, exist_ok=True)
os.makedirs(REVIEW_IMAGE_DIR, exist_ok=True)


# ============================================================
# SESSION
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
# HELPER: EXTRACT ITEM ID
# ============================================================

def extract_item_id(product_url):
    """
    Extract Daraz item ID from product URL.

    Example:
    ...-i537147546-s12644877285.html

    Returns:
        537147546
    """

    match = re.search(r"-i(\d+)-s\d+\.html", product_url)

    if match:
        return match.group(1)

    # Fallback
    match = re.search(r"-i(\d+)", product_url)

    if match:
        return match.group(1)

    return None


# ============================================================
# HELPER: BENGALI DETECTION
# ============================================================

def contains_bengali(text):
    """
    Returns True if the text contains at least one
    Bengali Unicode character.

    Bengali Unicode block:
        U+0980 - U+09FF
    """

    if not text:
        return False

    return bool(re.search(r"[\u0980-\u09FF]", text))


# ============================================================
# HELPER: CLEAN REVIEW TEXT
# ============================================================

def clean_review_text(text):
    """
    Basic whitespace cleaning.

    Does NOT translate or modify the language.
    """

    if not text:
        return ""

    text = str(text)

    # Replace newlines/tabs with spaces
    text = re.sub(r"[\r\n\t]+", " ", text)

    # Collapse repeated spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# HELPER: DOWNLOAD IMAGE
# ============================================================

def download_image(url, save_path):

    try:

        response = session.get(
            url,
            timeout=30
        )

        response.raise_for_status()

        with open(save_path, "wb") as f:
            f.write(response.content)

        return True

    except Exception as e:

        print(f"      Image download failed: {e}")

        return False


# ============================================================
# GET FIRST REVIEW PAGE
# ============================================================

def get_review_page(item_id, page_no):

    api_url = (
        "https://my.daraz.com.bd/pdp/review/getReviewList"
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
            f"Page {page_no}: HTTP {response.status_code}"
        )

        response.raise_for_status()

        return response.json()

    except Exception as e:

        print(f"ERROR getting page {page_no}: {e}")

        return None


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("DARAZ BENGALI ELECTRONICS SCRAPER V3")
    print("=" * 60)

    # --------------------------------------------------------
    # READ PRODUCT URLS
    # --------------------------------------------------------

    if not os.path.exists(INPUT_FILE):

        print(f"\nERROR: {INPUT_FILE} not found.")

        print(
            "\nCreate product_urls.txt and put one "
            "Daraz product URL per line."
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

        print("\nNo product URLs found.")

        return


    print(
        f"\nProducts to process: {len(product_urls)}"
    )


    # --------------------------------------------------------
    # CSV STORAGE
    # --------------------------------------------------------

    all_rows = []

    product_counter = 1
    review_counter = 1

    total_reviews_seen = 0
    total_bengali_reviews = 0
    total_empty_reviews = 0
    total_non_bengali_reviews = 0
    total_reviews_with_images = 0
    total_reviews_without_images = 0


    # --------------------------------------------------------
    # PROCESS PRODUCTS
    # --------------------------------------------------------

    for product_url in product_urls:

        print("\n" + "=" * 60)
        print("PROCESSING PRODUCT")
        print("=" * 60)

        print(f"URL: {product_url}")


        # ----------------------------------------------------
        # EXTRACT ITEM ID
        # ----------------------------------------------------

        item_id = extract_item_id(product_url)

        if not item_id:

            print(
                "ERROR: Could not extract Daraz item ID."
            )

            continue

        print(f"Daraz item ID: {item_id}")


        # ----------------------------------------------------
        # GET FIRST PAGE
        # ----------------------------------------------------

        print("\nGetting first review page...")

        first_page = get_review_page(
            item_id,
            1
        )

        if not first_page:

            print(
                "Could not retrieve first page. "
                "Skipping product."
            )

            continue


        # ----------------------------------------------------
        # EXTRACT MODEL
        # ----------------------------------------------------

        model = first_page.get("model", {})

        items = model.get("items") or []

        paging = model.get("paging") or {}

        total_pages = paging.get(
            "totalPages",
            1
        )

        total_items = paging.get(
            "totalItems",
            len(items)
        )


        print("\n" + "-" * 60)
        print("PRODUCT INFORMATION")
        print("-" * 60)

        print(
            f"Reviews reported by API: {total_items}"
        )

        print(
            f"Total pages: {total_pages}"
        )


        # ----------------------------------------------------
        # PRODUCT INFORMATION
        # ----------------------------------------------------

        if items:

            first_review = items[0]

            product_title = (
                first_review.get("itemTitle")
                or ""
            )

            product_image_url = (
                first_review.get("itemPic")
                or ""
            )

            api_product_url = (
                first_review.get("itemUrl")
                or product_url
            )

        else:

            product_title = ""

            product_image_url = ""

            api_product_url = product_url


        product_id = (
            f"PD{product_counter:02d}"
        )

        product_counter += 1


        print(
            f"Product ID: {product_id}"
        )

        print(
            f"Product title: {product_title}"
        )


        # ----------------------------------------------------
        # DOWNLOAD PRODUCT IMAGE
        # ----------------------------------------------------

        product_image_path = ""

        if product_image_url:

            product_extension = ".jpg"

            parsed_path = urlparse(
                product_image_url
            ).path

            extension = os.path.splitext(
                parsed_path
            )[1].lower()

            if extension in [
                ".jpg",
                ".jpeg",
                ".png",
                ".webp"
            ]:

                product_extension = extension


            product_filename = (
                f"{product_id}{product_extension}"
            )

            product_local_path = os.path.join(
                PRODUCT_IMAGE_DIR,
                product_filename
            )


            print("\nDownloading product image...")

            if os.path.exists(product_local_path):

                print(
                    "  Product image already exists."
                )

                product_image_path = (
                    product_local_path
                )

            else:

                success = download_image(
                    product_image_url,
                    product_local_path
                )

                if success:

                    print(
                        f"  Product image saved: "
                        f"{product_local_path}"
                    )

                    product_image_path = (
                        product_local_path
                    )


        # ----------------------------------------------------
        # PROCESS ALL PAGES
        # ----------------------------------------------------

        for page_no in range(
            1,
            total_pages + 1
        ):

            print("\n" + "-" * 60)

            print(
                f"PROCESSING PAGE "
                f"{page_no}/{total_pages}"
            )

            print("-" * 60)


            # Use first-page data for page 1
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
                    f"Skipping page {page_no}"
                )

                continue


            page_model = (
                page_data.get("model", {})
            )

            reviews = (
                page_model.get("items")
                or []
            )


            print(
                f"Reviews on this page: "
                f"{len(reviews)}"
            )


            # ------------------------------------------------
            # PROCESS EACH REVIEW
            # ------------------------------------------------

            for review in reviews:

                total_reviews_seen += 1


                review_text = (
                    review.get("reviewContent")
                    or ""
                )

                review_text = clean_review_text(
                    review_text
                )


                # ============================================
                # RULE 1: EMPTY REVIEW
                # ============================================

                if not review_text:

                    total_empty_reviews += 1

                    print(
                        "\n[REMOVED - EMPTY REVIEW]"
                    )

                    continue


                # ============================================
                # RULE 2: BENGALI FILTER
                # ============================================

                if not contains_bengali(
                    review_text
                ):

                    total_non_bengali_reviews += 1

                    print(
                        "\n[REMOVED - NON-BENGALI]"
                    )

                    print(
                        f"  Text: {review_text}"
                    )

                    continue


                # ============================================
                # BENGALI REVIEW
                # ============================================

                total_bengali_reviews += 1


                review_id = (
                    f"RV{review_counter:02d}"
                )

                review_counter += 1


                rating = review.get(
                    "rating",
                    ""
                )

                verified_purchase = review.get(
                    "isPurchased",
                    ""
                )


                # ============================================
                # REVIEW IMAGES
                # ============================================

                images = (
                    review.get("images")
                    or []
                )


                review_image_urls = []

                review_image_paths = []


                if images:

                    total_reviews_with_images += 1

                else:

                    total_reviews_without_images += 1


                review_folder = os.path.join(
                    REVIEW_IMAGE_DIR,
                    review_id
                )


                if images:

                    os.makedirs(
                        review_folder,
                        exist_ok=True
                    )


                # --------------------------------------------
                # DOWNLOAD REVIEW IMAGES
                # --------------------------------------------

                for image_index, image in enumerate(
                    images,
                    start=1
                ):

                    if not image:

                        continue


                    image_url = (
                        image.get("url")
                        or ""
                    )


                    if not image_url:

                        continue


                    review_image_urls.append(
                        image_url
                    )


                    # Determine extension
                    parsed_path = urlparse(
                        image_url
                    ).path

                    extension = os.path.splitext(
                        parsed_path
                    )[1].lower()


                    if extension not in [
                        ".jpg",
                        ".jpeg",
                        ".png",
                        ".webp"
                    ]:

                        extension = ".jpg"


                    image_filename = (
                        f"img_{image_index:02d}"
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


                # ============================================
                # SAVE REVIEW ROW
                # ============================================

                row = {

                    "review_id":
                        review_id,

                    "product_id":
                        product_id,

                    "marketplace":
                        "Daraz",

                    "product_title":
                        product_title,

                    "product_url":
                        api_product_url,

                    "product_image_url":
                        product_image_url,

                    "product_image_path":
                        product_image_path,

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


                all_rows.append(row)


                # ============================================
                # PRINT KEPT REVIEW
                # ============================================

                print("\n[KEPT - BENGALI REVIEW]")

                print(
                    f"Review ID : {review_id}"
                )

                print(
                    f"Rating    : {rating}"
                )

                print(
                    f"Purchased : {verified_purchase}"
                )

                print(
                    f"Text      : {review_text}"
                )

                print(
                    f"Images    : {len(images)}"
                )


        print(
            f"\nFinished product: "
            f"{product_id}"
        )


    # ========================================================
    # SAVE CSV
    # ========================================================

    print("\n" + "=" * 60)
    print("SAVING DATASET")
    print("=" * 60)


    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )


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

        writer.writerows(
            all_rows
        )


    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("\n" + "=" * 60)
    print("V3 SCRAPING COMPLETE")
    print("=" * 60)

    print(
        f"\nTotal reviews seen       : "
        f"{total_reviews_seen}"
    )

    print(
        f"Bengali reviews kept    : "
        f"{total_bengali_reviews}"
    )

    print(
        f"Empty reviews removed   : "
        f"{total_empty_reviews}"
    )

    print(
        f"Non-Bengali removed     : "
        f"{total_non_bengali_reviews}"
    )

    print(
        f"Kept reviews with image : "
        f"{total_reviews_with_images}"
    )

    print(
        f"Kept reviews no image   : "
        f"{total_reviews_without_images}"
    )

    print(
        f"\nFinal dataset rows      : "
        f"{len(all_rows)}"
    )

    print(
        f"CSV saved at            : "
        f"{CSV_FILE}"
    )

    print("\nDuplicates were NOT removed.")

    print(
        "REAL/FAKE labels were NOT assigned."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()