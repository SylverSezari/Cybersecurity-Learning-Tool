#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a word-list file containing only entries of a requested length."""


def filter_words_by_length(input_file, output_file, target_length=8):
    """
    Filter words from a file to keep only those with the specified length.

    Args:
        input_file (str): Path to the input file containing words (one per line)
        output_file (str): Path to the output file for filtered words
        target_length (int): Target word length (default is 8)
    """
    try:
        with open(input_file, "r", encoding="utf-8") as infile:
            words = [line.strip() for line in infile if line.strip()]

        # Filter words by the target length
        filtered_words = [word for word in words if len(word) == target_length]

        # Write filtered words to output file
        with open(output_file, "w", encoding="utf-8") as outfile:
            outfile.writelines(word + "\n" for word in filtered_words)

        print("Processing complete!")
        print(f"Original word count: {len(words)}")
        print(f"Filtered word count (length {target_length}): {len(filtered_words)}")
        print(f"Results saved to: {output_file}")

    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")


def main():
    """Main function to demonstrate usage"""
    # Example usage - you can modify these paths as needed
    input_file = "german_words.txt"  # Replace with your actual input file name
    output_file = "german_words_4letters.txt"

    print("Filtering German words to keep only those with 8 letters...")
    filter_words_by_length(input_file, output_file, 4)


if __name__ == "__main__":
    main()
