import sys

def to_sentence_case(text):
    # Split the text at common sentence-ending punctuations (., !, ?)
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    capitalized_sentences = []
    
    for sentence in sentences:
        if sentence:
            # Split the sentence into words
            words = sentence.split()
            # Capitalize the first word, lowercase the rest, but ensure 'I' remains capitalized
            capitalized_words = [words[0].capitalize()]
            for word in words[1:]:
                if word.lower() == 'i':
                    capitalized_words.append('I')
                else:
                    capitalized_words.append(word.lower())
            capitalized_sentence = ' '.join(capitalized_words)
            capitalized_sentences.append(capitalized_sentence)
    
    # Join the sentences back together with periods
    result = '. '.join(capitalized_sentences)

    # Add a period at the end if there isn't one
    if not result.endswith('.'):
        result += '.'

    return result

def to_lowercase(text):
    return text.lower()

def to_uppercase(text):
    return text.upper()

def process_text(text, operation):
    return operation(text)

def main():
    # Validate command-line arguments
    if len(sys.argv) != 2 or sys.argv[1] not in ["sentence", "lower", "upper"]:
        print("Usage: python script_name.py [sentence|lower|upper]")
        sys.exit(1)

    # Choose the appropriate operation based on the command-line argument
    if sys.argv[1] == "sentence":
        operation = to_sentence_case
    elif sys.argv[1] == "lower":
        operation = to_lowercase
    else:
        operation = to_uppercase

    # Read the input file
    with open('input.txt', 'r') as file:
        content = file.read()

    # Process the text
    processed_content = process_text(content, operation)

    # Save the processed content to an output file
    with open('output.txt', 'w') as file:
        file.write(processed_content)

    print(f"Processing complete using {sys.argv[1]} mode. Check 'output.txt' for the result.")

if __name__ == '__main__':
    main()

