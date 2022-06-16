import eval7
import random
NUMS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K']
SUITS = ['s', 'c', 'd', 'h']
FULL_DECK = []

for i in range(13):
    for j in range(4):
        FULL_DECK.append(NUMS[i] + SUITS[j])
calculated_df = pd.read_csv('hole_strengths.csv') # the values we computed offline, this df is slow to search through though
holes = calculated_df.Holes # the columns of our spreadsheet
strengths = calculated_df.Strengths
starting_strengths = dict(zip(holes, strengths))
def hole_list_to_key(self, hole):
        '''
    Converts a hole card list into a key that we can use to query our 
    strength dictionary

    hole: list - A list of two card strings in the engine's format (Kd, As, Th, 7d, etc.)
    '''
    card_1 = hole[0] # get all of our relevant info
    card_2 = hole[1]

    rank_1, suit_1 = card_1[0], card_1[1] # card info
    rank_2, suit_2 = card_2[0], card_2[1]

    numeric_1, numeric_2 = self.rank_to_numeric(rank_1), self.rank_to_numeric(rank_2) # make numeric

    suited = suit_1 == suit_2 # off-suit or not
    suit_string = 's' if suited else 'o'

    if numeric_1 >= numeric_2: # keep our hole cards in rank order
        return rank_1 + rank_2 + suit_string
    else:
        return rank_2 + rank_1 + suit_string
def rank_to_numeric(self, rank):
        '''
        Method that converts our given rank as a string
        into an integer ranking

        rank: str - one of 'A, K, Q, J, T, 9, 8, 7, 6, 5, 4, 3, 2'
        '''
    if rank.isnumeric(): # 2-9, we can just use the int version of this string
        return int(rank)
    elif rank == 'T': # 10 is T, so we need to specify it here
        return 10
    elif rank == 'J': # Face cards for the rest of them
        return 11
    elif rank == 'Q':
        return 12
    elif rank == 'K':
        return 13
    else: # Ace (A) is the only one left, give it the highest rank
        return 14
def sort_cards_by_rank(self, cards):
    '''
    Method that takes in a list of cards in the engine's format
    and sorts them by rank order

    cards: list - a list of card strings in the engine's format (Kd, As, Th, 7d, etc.)
    '''
    return sorted(cards, reverse=True, key=lambda x: self.rank_to_numeric(x[0])) 
def allocate_cards(self, my_cards):
        '''
        Method that allocates our cards at the beginning of a round. Method
        modifies self.board_allocations. The method attempts to make pairs
        by allocating hole cards that share a rank if possible. The exact
        stack these cards are allocated to is not defined.

        Arguments:
        my_cards: a list of the 6 cards given to us at round start
        '''
    my_cards = self.sort_cards_by_rank(my_cards)
    holes_allocated = []
    for _ in range(3):
        max_strength_hole = 0
        temp_cards = []

        for i in range(len(my_cards)-1):
            for j in range(i+1, len(my_cards)):
                hole_list = [my_cards[i], my_cards[j]]
                temp_hole = self.hole_list_to_key(hole_list)
                strength = self.starting_strengths[temp_hole]

                if strength > max_strength_hole:
                    temp_cards = hole_list
                    max_strength_hole = strength

        holes_allocated.append(temp_cards)
        my_cards.remove(temp_cards[0]) 
        my_cards.remove(temp_cards[1])

    return holes_allocated # return our decisions
if  __name__ == "__main__":
    strength1, strength2. strength3 = 0, 0, 0
    for i in range (10000):
        cards = random.sample(FULL_DECK, 6))
        holelist = allocate_cards(cards)
        strength1 += starting_strengths[hole_list_to_key(holelist[2])]
        strength2 += starting_strengths[hole_list_to_key(holelist[1])]
        strength3 += starting_strengths[hole_list_to_key(holelist[0])]
    
    print(strength1/10000)
    print(strength2/10000)
    print(strength3/10000)