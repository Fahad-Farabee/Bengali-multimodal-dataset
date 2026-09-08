import os
import re
import csv
import sys
import requests
from urllib.parse import urlparse


# ============================================================
# CONFIGURATION
# ============================================================

PRODUCT_URL = (
    "https://www.daraz.com.bd/products/"
    "hoco-eq24-estrella-wireless-bt-earbuds-time-square"
    "-i537147546-s12644877285.html"
)

PAGE_SIZE = 5

OUTPUT_DIR = "output"
PRODUCT_IMAGE_DIR = os.path.join(OUTPUT_DIR, "images", "products")
REVIEW_IMAGE_DIR = os.path.join(OUTPUT_DIR, "images", "reviews")

CSV_FILE = os.path.join(OUTPUT_DIR, "reviews.csv")


# ============================================================
# WINDOWS UTF-8 SUPPORT
# ============================================================

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


# ============================================================
# HTTP HEADERS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": PRODUCT_URL,
}


# ============================================================
# CREATE FOLDERS
# ============================================================

os.makedirs(PRODUCT_IMAGE_DIR, exist_ok=True)
os.makedirs(REVIEW_IMAGE_DIR, exist_ok=True)


# ============================================================
# EXTRACT DARAZ ITEM ID
# ============================================================

def extract_item_id(product_url):

    match = re.search(r"-i(\d+)-s\d+\.html", product_url)

    if not match:
        raise ValueError(
            "Could not find Daraz item ID in the product URL."
        )

    return match.group(1)


# ============================================================
# DOWNLOAD IMAGE
# ============================================================

def download_image(image_url, filepath):

    if not image_url:
        return False

    try:

        response = requests.get(
            image_url,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        with open(filepath, "wb") as file:
            file.write(response.content)

        return True

    except requests.RequestException as error:

        print(f"      Image download failed: {error}")

        return False


# ============================================================
# GET FILE EXTENSION
# ============================================================

def get_extension(image_url):

    path = urlparse(image_url).path

    extension = os.path.splitext(path)[1].lower()

    if extension in [".jpg", ".jpeg", ".png", ".webp"]:
        return extension

    return ".jpg"


# ============================================================
# DOWNLOAD PRODUCT IMAGE
# ============================================================

def download_product_image(product_id, image_url):

    if not image_url:
        return ""

    extension = get_extension(image_url)

    filename = f"{product_id}{extension}"

    filepath = os.path.join(
        PRODUCT_IMAGE_DIR,
        filename
    )

    # Don't download again if already exists
    if os.path.exists(filepath):

        print(f"  Product image already exists: {filepath}")

        return filepath

    print("\nDownloading product image...")

    success = download_image(
        image_url,
        filepath
    )

    if success:

        print(f"  Product image saved: {filepath}")

        return filepath

    return ""


# ============================================================
# DOWNLOAD REVIEW IMAGES
# ============================================================

def download_review_images(
    review_id,
    image_urls
):

    if not image_urls:
        return []

    review_folder = os.path.join(
        REVIEW_IMAGE_DIR,
        review_id
    )

    os.makedirs(
        review_folder,
        exist_ok=True
    )

    local_paths = []

    for index, image_url in enumerate(
        image_urls,
        start=1
    ):

        extension = get_extension(image_url)

        filename = (
            f"img_{index:02d}{extension}"
        )

        filepath = os.path.join(
            review_folder,
            filename
        )

        print(
            f"      Downloading review image "
            f"{index}..."
        )

        success = download_image(
            image_url,
            filepath
        )

        if success:

            print(
                f"      Saved: {filepath}"
            )

            local_paths.append(filepath)

    return local_paths


# ============================================================
# REQUEST ONE REVIEW PAGE
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

        response = requests.get(
            api_url,
            params=params,
            headers=HEADERS,
            timeout=30
        )

        print(
            f"Page {page_no}: "
            f"HTTP {response.status_code}"
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as error:

        print(
            f"ERROR requesting page "
            f"{page_no}: {error}"
        )

        return None

    except ValueError:

        print(
            f"ERROR: Page {page_no} "
            f"did not return valid JSON."
        )

        return None


# ============================================================
# SAVE CSV
# ============================================================

def save_csv(rows):

    fieldnames = [

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

    with open(
        CSV_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(rows)

    print("\n============================================")
    print("CSV CREATED")
    print("============================================")

    print(f"File: {CSV_FILE}")
    print(f"Rows: {len(rows)}")


# ============================================================
# MAIN SCRAPER
# ============================================================

def main():

    print("============================================")
    print("DARAZ EXPERIMENTAL SCRAPER")
    print("============================================")

    print("\nProduct:")
    print(PRODUCT_URL)

    # --------------------------------------------------------
    # STEP 1: Extract item ID
    # --------------------------------------------------------

    try:

        item_id = extract_item_id(
            PRODUCT_URL
        )

    except ValueError as error:

        print(error)

        return

    print(
        f"\nDaraz item ID: {item_id}"
    )

    # --------------------------------------------------------
    # STEP 2: Get first page
    # --------------------------------------------------------

    print(
        "\nGetting first review page..."
    )

    first_data = get_review_page(
        item_id,
        1
    )

    if not first_data:

        print(
            "Could not retrieve reviews."
        )

        return

    if first_data.get("success") is not True:

        print(
            "Daraz API returned "
            "success=False."
        )

        return

    model = first_data.get(
        "model",
        {}
    )

    paging = model.get(
        "paging",
        {}
    )

    total_reviews = paging.get(
        "totalItems",
        0
    )

    total_pages = paging.get(
        "totalPages",
        0
    )

    print("\n============================================")
    print("REVIEW INFORMATION")
    print("============================================")

    print(
        f"Total reviews : {total_reviews}"
    )

    print(
        f"Total pages   : {total_pages}"
    )

    # --------------------------------------------------------
    # STEP 3: Get product information
    # --------------------------------------------------------

    first_reviews = model.get(
        "items",
        []
    )

    if not first_reviews:

        print(
            "No reviews found."
        )

        return

    first_review = first_reviews[0]

    product_id = item_id

    product_title = first_review.get(
        "itemTitle",
        ""
    )

    product_url = first_review.get(
        "itemUrl",
        PRODUCT_URL
    )

    product_image_url = first_review.get(
        "itemPic",
        ""
    )

    # --------------------------------------------------------
    # STEP 4: Create our internal product ID
    # --------------------------------------------------------

    internal_product_id = "PD01"

    print(
        f"\nProduct ID: {internal_product_id}"
    )

    print(
        f"Product title: {product_title}"
    )

    # --------------------------------------------------------
    # STEP 5: Download product image
    # --------------------------------------------------------

    product_image_path = (
        download_product_image(
            internal_product_id,
            product_image_url
        )
    )

    # --------------------------------------------------------
    # STEP 6: Process every review page
    # --------------------------------------------------------

    all_rows = []

    review_counter = 0

    for page_no in range(
        1,
        total_pages + 1
    ):

        print("\n--------------------------------------------")
        print(
            f"PROCESSING PAGE "
            f"{page_no}/{total_pages}"
        )
        print("--------------------------------------------")

        # First page already downloaded
        if page_no == 1:

            data = first_data

        else:

            data = get_review_page(
                item_id,
                page_no
            )

        if not data:

            print(
                f"Skipping page {page_no}"
            )

            continue

        model = data.get(
            "model",
            {}
        )

        reviews = model.get(
            "items",
            []
        )

        print(
            f"Reviews on this page: "
            f"{len(reviews)}"
        )

        # ----------------------------------------------------
        # Process individual reviews
        # ----------------------------------------------------

        for review in reviews:

            review_counter += 1

            review_id = (
                f"RV{review_counter:02d}"
            )

            rating = review.get(
                "rating"
            )

            review_text = review.get(
                "reviewContent",
                ""
            )

            review_date = review.get(
                "reviewTime"
            )

            verified_purchase = review.get(
                "isPurchased"
            )

            # -----------------------------------------------
            # Review image URLs
            # -----------------------------------------------

            image_urls = []

            images = review.get("images") or []

            for image in images:
                image_url = image.get("url")

                if image_url:
                    image_urls.append(image_url)

            # -----------------------------------------------
            # Download review images
            # -----------------------------------------------

            local_image_paths = (
                download_review_images(
                    review_id,
                    image_urls
                )
            )

            # -----------------------------------------------
            # Print review
            # -----------------------------------------------

            print(
                f"\nReview: {review_id}"
            )

            print(
                f"  Rating    : {rating}"
            )

            print(
                f"  Purchased : "
                f"{verified_purchase}"
            )

            print(
                f"  Text      : "
                f"{review_text}"
            )

            print(
                f"  Images    : "
                f"{len(image_urls)}"
            )

            # -----------------------------------------------
            # Create CSV row
            # -----------------------------------------------

            row = {

                "review_id":
                    review_id,

                "product_id":
                    internal_product_id,

                "marketplace":
                    "Daraz",

                "product_title":
                    product_title,

                "product_url":
                    product_url,

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
                        image_urls
                    ),

                "review_image_paths":
                    " | ".join(
                        local_image_paths
                    ),

                "verified_purchase":
                    verified_purchase,

                "annotator_id":
                    "",

                "final_label":
                    ""
            }

            all_rows.append(row)

    # --------------------------------------------------------
    # STEP 7: Save CSV
    # --------------------------------------------------------

    save_csv(all_rows)

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print("\n============================================")
    print("SCRAPING COMPLETED")
    print("============================================")

    print(
        f"Product: "
        f"{internal_product_id}"
    )

    print(
        f"Reviews collected: "
        f"{len(all_rows)}"
    )

    print(
        f"Product image: "
        f"{product_image_path}"
    )

    print(
        f"CSV: "
        f"{CSV_FILE}"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()