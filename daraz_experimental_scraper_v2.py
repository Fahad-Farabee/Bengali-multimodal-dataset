import os
import re
import csv
import sys
import time
import requests
from urllib.parse import urlparse


# ============================================================
# CONFIGURATION
# ============================================================

URL_FILE = "product_urls.txt"

PAGE_SIZE = 5

OUTPUT_DIR = "output_v2"

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

CSV_FILE = os.path.join(
    OUTPUT_DIR,
    "reviews.csv"
)

# Small delay between API requests
REQUEST_DELAY = 1


# ============================================================
# WINDOWS UTF-8 SUPPORT
# ============================================================

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


# ============================================================
# HEADERS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*"
}


# ============================================================
# CREATE DIRECTORIES
# ============================================================

os.makedirs(
    PRODUCT_IMAGE_DIR,
    exist_ok=True
)

os.makedirs(
    REVIEW_IMAGE_DIR,
    exist_ok=True
)


# ============================================================
# READ PRODUCT URLS
# ============================================================

def load_product_urls():

    if not os.path.exists(URL_FILE):

        print(
            f"ERROR: {URL_FILE} not found."
        )

        return []

    urls = []

    with open(
        URL_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        for line in file:

            url = line.strip()

            # Ignore empty lines
            if not url:
                continue

            # Ignore comments
            if url.startswith("#"):
                continue

            urls.append(url)

    return urls


# ============================================================
# EXTRACT DARAZ ITEM ID
# ============================================================

def extract_item_id(product_url):

    match = re.search(
        r"-i(\d+)-s\d+\.html",
        product_url
    )

    if not match:

        raise ValueError(
            "Could not find Daraz item ID "
            "in the product URL."
        )

    return match.group(1)


# ============================================================
# GET IMAGE EXTENSION
# ============================================================

def get_extension(image_url):

    path = urlparse(
        image_url
    ).path

    extension = os.path.splitext(
        path
    )[1].lower()

    if extension in [
        ".jpg",
        ".jpeg",
        ".png",
        ".webp"
    ]:

        return extension

    return ".jpg"


# ============================================================
# DOWNLOAD IMAGE
# ============================================================

def download_image(
    image_url,
    filepath
):

    if not image_url:

        return False

    try:

        response = requests.get(
            image_url,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        with open(
            filepath,
            "wb"
        ) as file:

            file.write(
                response.content
            )

        return True

    except requests.RequestException as error:

        print(
            f"      Image download failed: "
            f"{error}"
        )

        return False


# ============================================================
# DOWNLOAD PRODUCT IMAGE
# ============================================================

def download_product_image(
    product_id,
    image_url
):

    if not image_url:

        return ""

    extension = get_extension(
        image_url
    )

    filepath = os.path.join(
        PRODUCT_IMAGE_DIR,
        f"{product_id}{extension}"
    )

    # Don't download again
    if os.path.exists(filepath):

        print(
            f"Product image already exists: "
            f"{filepath}"
        )

        return filepath

    print(
        "Downloading product image..."
    )

    success = download_image(
        image_url,
        filepath
    )

    if success:

        print(
            f"Product image saved: "
            f"{filepath}"
        )

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

        extension = get_extension(
            image_url
        )

        filename = (
            f"img_{index:02d}{extension}"
        )

        filepath = os.path.join(
            review_folder,
            filename
        )

        # Don't download again
        if os.path.exists(filepath):

            print(
                f"      Already exists: "
                f"{filepath}"
            )

            local_paths.append(
                filepath
            )

            continue

        print(
            f"      Downloading review "
            f"image {index}..."
        )

        success = download_image(
            image_url,
            filepath
        )

        if success:

            print(
                f"      Saved: {filepath}"
            )

            local_paths.append(
                filepath
            )

    return local_paths


# ============================================================
# REQUEST REVIEW PAGE
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
            f"returned invalid JSON."
        )

        return None


# ============================================================
# PROCESS ONE PRODUCT
# ============================================================

def scrape_product(
    product_url,
    internal_product_id,
    review_counter
):

    print("\n")
    print("=" * 60)
    print(
        f"PRODUCT {internal_product_id}"
    )
    print("=" * 60)

    print(
        f"URL:\n{product_url}"
    )

    # --------------------------------------------------------
    # Extract Daraz item ID
    # --------------------------------------------------------

    try:

        item_id = extract_item_id(
            product_url
        )

    except ValueError as error:

        print(
            f"ERROR: {error}"
        )

        return [], review_counter

    print(
        f"\nDaraz item ID: {item_id}"
    )

    # --------------------------------------------------------
    # Request first page
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

        return [], review_counter

    if first_data.get(
        "success"
    ) is not True:

        print(
            "Daraz API returned "
            "success=False."
        )

        return [], review_counter

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

    first_reviews = model.get(
        "items",
        []
    )

    print("\n--------------------------------------------")
    print("PRODUCT REVIEW INFORMATION")
    print("--------------------------------------------")

    print(
        f"Daraz item ID : {item_id}"
    )

    print(
        f"Total ratings : {total_reviews}"
    )

    print(
        f"Total pages   : {total_pages}"
    )

    print(
        f"Page 1 reviews: "
        f"{len(first_reviews)}"
    )

    # --------------------------------------------------------
    # If no reviews
    # --------------------------------------------------------

    if not first_reviews:

        print(
            "No review records returned."
        )

        return [], review_counter

    # --------------------------------------------------------
    # Product information
    # --------------------------------------------------------

    first_review = first_reviews[0]

    product_title = first_review.get(
        "itemTitle",
        ""
    )

    actual_product_url = first_review.get(
        "itemUrl",
        product_url
    )

    product_image_url = first_review.get(
        "itemPic",
        ""
    )

    print(
        f"\nProduct title:\n"
        f"{product_title}"
    )

    # --------------------------------------------------------
    # Download product image
    # --------------------------------------------------------

    product_image_path = (
        download_product_image(
            internal_product_id,
            product_image_url
        )
    )

    # --------------------------------------------------------
    # Process pages
    # --------------------------------------------------------

    all_rows = []

    for page_no in range(
        1,
        total_pages + 1
    ):

        print("\n--------------------------------------------")
        print(
            f"{internal_product_id} - "
            f"PROCESSING PAGE "
            f"{page_no}/{total_pages}"
        )
        print("--------------------------------------------")

        # First page already retrieved
        if page_no == 1:

            data = first_data

        else:

            time.sleep(
                REQUEST_DELAY
            )

            data = get_review_page(
                item_id,
                page_no
            )

        if not data:

            print(
                f"Skipping page {page_no}"
            )

            continue

        page_model = data.get(
            "model",
            {}
        )

        reviews = page_model.get(
            "items",
            []
        )

        print(
            f"Reviews returned: "
            f"{len(reviews)}"
        )

        # ----------------------------------------------------
        # Process reviews
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

            verified_purchase = (
                review.get(
                    "isPurchased"
                )
            )

            # ------------------------------------------------
            # Review images
            # ------------------------------------------------

            images = (
                review.get("images")
                or []
            )

            image_urls = []

            for image in images:

                if not isinstance(
                    image,
                    dict
                ):
                    continue

                image_url = image.get(
                    "url"
                )

                if image_url:

                    image_urls.append(
                        image_url
                    )

            # ------------------------------------------------
            # Download review images
            # ------------------------------------------------

            local_image_paths = (
                download_review_images(
                    review_id,
                    image_urls
                )
            )

            # ------------------------------------------------
            # Print review information
            # ------------------------------------------------

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
                f"  Images    : "
                f"{len(image_urls)}"
            )

            print(
                f"  Text      : "
                f"{review_text}"
            )

            # ------------------------------------------------
            # CSV row
            # ------------------------------------------------

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
                    actual_product_url,

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

            all_rows.append(
                row
            )

    print("\n============================================")
    print(
        f"{internal_product_id} COMPLETED"
    )
    print("============================================")

    print(
        f"Reviews collected: "
        f"{len(all_rows)}"
    )

    return (
        all_rows,
        review_counter
    )


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

        writer.writerows(
            rows
        )

    print("\n============================================")
    print("CSV CREATED")
    print("============================================")

    print(
        f"File: {CSV_FILE}"
    )

    print(
        f"Rows: {len(rows)}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("============================================")
    print("DARAZ MULTI-PRODUCT SCRAPER - VERSION 2")
    print("============================================")

    # --------------------------------------------------------
    # Load URLs
    # --------------------------------------------------------

    product_urls = load_product_urls()

    if not product_urls:

        print(
            "\nNo product URLs found."
        )

        return

    print(
        f"\nProduct URLs found: "
        f"{len(product_urls)}"
    )

    # --------------------------------------------------------
    # Show URLs
    # --------------------------------------------------------

    for index, url in enumerate(
        product_urls,
        start=1
    ):

        print(
            f"{index}. {url}"
        )

    # --------------------------------------------------------
    # Global counters
    # --------------------------------------------------------

    all_rows = []

    review_counter = 0

    product_counter = 0

    # --------------------------------------------------------
    # Process every product
    # --------------------------------------------------------

    for product_url in product_urls:

        product_counter += 1

        internal_product_id = (
            f"PD{product_counter:02d}"
        )

        try:

            rows, review_counter = (
                scrape_product(
                    product_url,
                    internal_product_id,
                    review_counter
                )
            )

            all_rows.extend(
                rows
            )

        except Exception as error:

            print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print(
                f"ERROR processing "
                f"{internal_product_id}"
            )

            print(
                f"{error}"
            )

            print(
                "Moving to next product..."
            )

            print(
                "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            )

    # --------------------------------------------------------
    # Save final CSV
    # --------------------------------------------------------

    save_csv(
        all_rows
    )

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    print("\n")
    print("=" * 60)
    print("FINAL SCRAPING SUMMARY")
    print("=" * 60)

    print(
        f"Products processed : "
        f"{product_counter}"
    )

    print(
        f"Reviews collected  : "
        f"{len(all_rows)}"
    )

    print(
        f"CSV file           : "
        f"{CSV_FILE}"
    )

    print("=" * 60)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()