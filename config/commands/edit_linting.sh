# @yaml
# signature: |-
#   edit <start_line>:<end_line>
#   <replacement_text>
#   end_of_edit
# docstring: replaces lines <start_line> through <end_line> (inclusive) with the given text in the open file. The replacement text is terminated by a line with only end_of_edit on it. All of the <replacement text> will be entered, so make sure your indentation is formatted properly. Python files will be checked for syntax errors after the edit. If the system detects a syntax error, the edit will not be executed. Simply try to edit the file again, but make sure to read the error message and modify the edit command you issue accordingly. Issuing the same command a second time will just lead to the same error message again.
# end_name: end_of_edit
# arguments:
#   start_line:
#     type: integer
#     description: the line number to start the edit at
#     required: true
#   end_line:
#     type: integer
#     description: the line number to end the edit at (inclusive)
#     required: true
#   replacement_text:
#     type: string
#     description: the text to replace the current selection with
#     required: true
edit() {
    if [ -z "$CURRENT_FILE" ]
    then
        echo 'No file open. Use the `open` command first.'
        return
    fi

    local start_line="$(echo $1: | cut -d: -f1)"
    local end_line="$(echo $1: | cut -d: -f2)"

    if [ -z "$start_line" ] || [ -z "$end_line" ]
    then
        echo "Usage: edit <start_line>:<end_line>"
        return
    fi

    local re='^[0-9]+$'
    if ! [[ $start_line =~ $re ]]; then
        echo "Usage: edit <start_line>:<end_line>"
        echo "Error: start_line must be a number"
        return
    fi
    if ! [[ $end_line =~ $re ]]; then
        echo "Usage: edit <start_line>:<end_line>"
        echo "Error: end_line must be a number"
        return
    fi

    local linter_cmd="flake8 --isolated --select=F822,F831,E111,E112,E113,E999,E902"
    local linter_cmd_no_block="flake8 --isolated --select=F821,F822,F831,E111,E112,E113,E999,E902"
    local linter_before_edit=$($linter_cmd "$CURRENT_FILE" 2>&1)
    local linter_no_block_before_edit=$($linter_cmd_no_block "$CURRENT_FILE" 2>&1)

    # Bash array starts at 0, so let's adjust
    local start_line=$((start_line - 1))
    local end_line=$((end_line))

    local line_count=0
    local replacement=()
    while IFS= read -r line
    do
        replacement+=("$line")
        ((line_count++))
    done

    # Create a backup of the current file
    cp "$CURRENT_FILE" "/root/$(basename "$CURRENT_FILE")_backup"

    # Read the file line by line into an array
    mapfile -t lines < "$CURRENT_FILE"
    local new_lines=("${lines[@]:0:$start_line}" "${replacement[@]}" "${lines[@]:$((end_line))}")
    # Write the new stuff directly back into the original file
    printf "%s\n" "${new_lines[@]}" >| "$CURRENT_FILE"

    # Run linter
    if [[ $CURRENT_FILE == *.py ]]; then
        _lint_output=$($linter_cmd "$CURRENT_FILE" 2>&1)
        lint_output=$(_split_string "$_lint_output" --previous "$linter_before_edit" --window "$((start_line+1))" "$end_line" --n-lines "$line_count")
        _lint_output_no_block=$($linter_cmd_no_block "$CURRENT_FILE" 2>&1)
        lint_output_no_block=$(_split_string "$_lint_output_no_block" --previous "$linter_no_block_before_edit" --window "$((start_line+1))" "$end_line" --n-lines "$line_count" --line-numbers)
    else
        # do nothing
        lint_output=""
    fi

    # if there is no output, then the file is good
    if [ -z "$lint_output" ]; then
        export CURRENT_LINE=$start_line
        _constrain_line
        _print
        echo "File updated. Please review the changes and make sure they are correct (correct indentation, no duplicate lines, etc). Edit the file again if necessary."
        if [ ! -z "$lint_output_no_block" ]; then
            echo ""
            echo "WARNING: Your changes have been applied, but the following warnings were issued:"
            echo "$lint_output_no_block"
            echo "It is very important that you fix these issues with the next edit."
            echo ""
        fi

    else
        echo "Your proposed edit has introduced new syntax error(s). Please read this error message carefully and then retry editing the file."
        echo ""
        echo "ERRORS:"
        echo "$lint_output"
        echo ""

        # Save original values
        original_current_line=$CURRENT_LINE
        original_window=$WINDOW

        # Update values
        export CURRENT_LINE=$(( (line_count / 2) + start_line )) # Set to "center" of edit
        export WINDOW=$((line_count + 10)) # Show +/- 5 lines around edit

        echo "This is how your edit would have looked if applied"
        echo "-------------------------------------------------"
        _constrain_line
        _print
        echo "-------------------------------------------------"
        echo ""

        # Restoring CURRENT_FILE to original contents.
        cp "/root/$(basename "$CURRENT_FILE")_backup" "$CURRENT_FILE"

        export CURRENT_LINE=$(( ((end_line - start_line + 1) / 2) + start_line ))
        export WINDOW=$((end_line - start_line + 10))

        echo "This is the original code before your edit."
        local start_line_ob=$((start_line + 1))
        echo "Your last edit command tried to replace lines $start_line_ob (inclusive) through $end_line."
        echo "Please carefully check that those are the right lines to edit."
        echo "-------------------------------------------------"
        _constrain_line
        _print
        echo "-------------------------------------------------"

        # Restore original values
        export CURRENT_LINE=$original_current_line
        export WINDOW=$original_window

        echo "Your changes have NOT been applied. Please fix your edit command and try again."
        echo "You need to either"
        echo "1) Specify the correct start/end line arguments. Even if the error mentions syntax errors or indentation errors, this is the most frequent cause of errors."
        echo "2) Correct your edit code (please make sure that the start/end line arguments are correct first)."
        echo "3) Try using several incremental smaller edits instead of one large edit."
        echo "DO NOT re-run the same failed edit command. Running it again will lead to the same error."
    fi

    # Remove backup file
    rm -f "/root/$(basename "$CURRENT_FILE")_backup"
}
