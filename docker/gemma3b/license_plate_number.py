from fuzzywuzzy import fuzz


def compare_entry_and_exit_license_plate(entry_plate, exit_plate):
    return fuzz.ratio(entry_plate, exit_plate)/100


