import os
import shutil

def move_files(src_folder, dest_folder):
    """Move all files from src_folder to dest_folder, if both exist."""
    if os.path.exists(src_folder):
        os.makedirs(dest_folder, exist_ok=True)  # Ensure destination folder exists

        for file_name in os.listdir(src_folder):
            src_file = os.path.join(src_folder, file_name)
            dst_file = os.path.join(dest_folder, file_name)

            shutil.move(src_file, dst_file)
            print(f"Moved: {src_file} → {dst_file}")

        # Remove empty source folder
        if not os.listdir(src_folder):
            os.rmdir(src_folder)
            print(f"Removed empty folder: {src_folder}")

def move_images(parent_directory, folder_mapping):
    """
    Moves all images from each source_folder to its corresponding destination_folder in each category.
    Also moves files from 'thumbnail/source_folder' → 'thumbnail/destination_folder'.
    """

    # Iterate through each category folder inside parent_directory
    for category in os.listdir(parent_directory):
        category_path = os.path.join(parent_directory, category)

        # Ensure it's a directory
        if os.path.isdir(category_path):
            for src_folder, dest_folder in folder_mapping.items():
                folder_src = os.path.join(category_path, src_folder)
                folder_dest = os.path.join(category_path, dest_folder)
                thumbnail_src = os.path.join(category_path, "thumbnail", src_folder)
                thumbnail_dest = os.path.join(category_path, "thumbnail", dest_folder)

                # Ensure destination folder exists before moving
                os.makedirs(folder_dest, exist_ok=True)
                
                # Move files from source_folder → destination_folder
                move_files(folder_src, folder_dest)

                # Move files from thumbnail/source_folder → thumbnail/destination_folder
                if os.path.exists(thumbnail_src):
                    os.makedirs(thumbnail_dest, exist_ok=True)  # Ensure thumbnail destination exists
                    move_files(thumbnail_src, thumbnail_dest)

if __name__ == "__main__":
    parent_directory = "../imageData"

    # Get user input for folder mappings (key-value format)
    mapping_input = "2548:1998,871:2554,778:2500,794:2529,2227:2599,1722:2567,1724:2557,1809:2589,930:2564,777:2526,779:2509,1808:2588,2228:2597,791:2540,783:2536,793:2546,784:2532,806:2534,799:2538,798:2541,802:2533,786:2545,774:2498,776:2513,1723:2582,869:2560,875:2566,670:2604,2282:2602,2770:2771,813:2549,2673:2526,810:2606,2680:2606,2:2608,2298:2700,371:2439,27:2611,2563:2689,28:2616,872:2704,868:2708,2660:1,350:41,2637:2661,2726:751,2703:2553,2613:16,2624:121,2234:2725,765:2668,2505:2670,560:567,2543:800,2609:31,2620:21,870:2702,2618:17,493:2478,383:2459,2671:2499,2674:2565,473:475,642:625,2610:19,2614:22,2663:752,2667:6,2010:1842,2612:18,2615:10"

    # Convert input string to a dictionary
    folder_mapping = {}
    for pair in mapping_input.split(","):
        key, value = pair.strip().split(":")
        folder_mapping[key.strip()] = value.strip()

    if os.path.exists(parent_directory) and os.path.isdir(parent_directory):
        move_images(parent_directory, folder_mapping)
        print("File moving process completed successfully!")
    else:
        print("Invalid directory. Please check the path and try again.")
