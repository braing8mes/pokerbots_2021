'''
AP Poker, written in Python.
'''
from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction, AssignAction
from skeleton.states import GameState, TerminalState, RoundState, BoardState
from skeleton.states import NUM_ROUNDS, STARTING_STACK, BIG_BLIND, SMALL_BLIND, NUM_BOARDS
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot

import eval7
import random


class Player(Bot):
    '''
    A pokerbot.
    '''

    def __init__(self):
        '''
        Called when a new game starts. Called exactly once.

        Arguments:
        Nothing.

        Returns:
        Nothing.
        '''
        self.allocations = [[], [], []]
        self.hole_strengths = [0, 0, 0]
        self.MONTE_CARLO_ITERS = 100 # the number of Monte Carlo samples we will use
    
    def rank_to_numeric(self, rank):
        if rank.isnumeric(): # 2-9
            return int(rank)
        elif rank == 'T': # 10 is T, so we need to specify it here
            return 10
        elif rank == 'J': # Face cards for the rest of them
            return 11
        elif rank == 'Q':
            return 12
        elif rank == 'K':
            return 13
        else: # Ace (A) is the only one left
            return 14

    def sort_cards_by_rank(self, cards):
        return sorted(cards, reverse = True, key = lambda x: self.rank_to_numeric(x[0])) # we want it in descending order

    def calculate_strength(self, hole, iters): 
        '''
        A Monte Carlo method meant to estimate the win probability of a pair of 
        hole cards. Simlulates 'iters' games and determines the win rates of our cards

        Arguments:
        hole: a list of our two hole cards
        iters: a integer that determines how many Monte Carlo samples to take

        Returns: win probability, expressed as a float between 0 and 1
        '''

        deck = eval7.Deck() # eval7 object!
        hole_cards = [eval7.Card(card) for card in hole] # card objects, used to evaliate hands

        for card in hole_cards: # remove cards that we know about! they shouldn't come up in simulations
            deck.cards.remove(card)

        score = 0

        for _ in range(iters): # take 'iters' samples
            deck.shuffle() # make sure our samples are random

            _COMM = 5 # the number of cards we need to draw
            _OPP = 2

            draw = deck.peek(_COMM + _OPP)

            opp_hole = draw[: _OPP]
            community = draw[_OPP: ]

            our_hand = hole_cards + community # the two showdown hands
            opp_hand = opp_hole + community

            our_hand_value = eval7.evaluate(our_hand) # the ranks of our hands (only useful for comparisons)
            opp_hand_value = eval7.evaluate(opp_hand)

            if our_hand_value > opp_hand_value: # we win!
                score += 2
            
            elif our_hand_value == opp_hand_value: # we tie.
                score += 1
            
            else: # we lost...
                score += 0
        
        hand_strength = score / (2 * iters) #this is our win probability!

        return hand_strength

    def allocate_cards(self, my_cards):
        '''
        Allocates cards by mutating passing in self.allocations as my_cards and mutating it

        Strategy: Allocate pairs together and assign to biggest board; next pair suits of singles
            otherwise, and sort any remaining singles by rank. 

        Arguments:
        my_cards

        Returns:
        Nothing.
        '''

        ranks = {}
        suits = {}

        for card in my_cards:
            card_rank = card[0]
            card_suit = card[1]

            if card_rank in ranks: # if card with same rank already seen
                ranks[card_rank].append(card)

            else: # map card_rank to new list containing current card
                ranks[card_rank] = [card]

            if card_suit in suits:
                suits[card_suit].append(card)

            else:
                suits[card_suit] = [card]
        
        singles = []
        pairs = []
        thirds = []

        for rank in ranks:
            cards = ranks[rank]

            if len(cards) == 2:
                pairs += cards

            elif len(cards) == 3: # TODO sort by number of suit repetitions
                suit_drawn = []
                suit_undrawn = []

                for card in cards:
                    if len(suits[card[1]]) > 1:
                        suit_drawn.append(card)
                    else:
                        suit_undrawn.append(card)

                ordered_cards = suit_drawn + suit_undrawn
                thirds.append(ordered_cards[0]) # set aside to put at lowest board
                pairs += ordered_cards[1], ordered_cards[2]
                        

            elif len(cards) == 4: # TODO sort by number of suit repetitions
                suit_drawn = []
                suit_undrawn = []

                for card in cards:
                    if len(suits[card[1]]) > 1:
                        suit_drawn.append(card)
                    else:
                        suit_undrawn.append(card)

                pairs += suit_drawn + suit_undrawn # if suit drawn, less prob of a flush so put first

            else: # single
                singles += cards

        ordered_ranks = sorted([card[0] for card in singles])
        ordered_singles = thirds # copy thirds at beginning of list
        
        while singles:
            for i in range(len(singles)):
                if singles[i][0] == ordered_ranks[0]:
                    ordered_ranks.pop(0)
                    ordered_singles.append(singles.pop(i)) # remove from list and append to ordered_singles
                    break # stop looping, otherwise will raise IndexError because of pop

        if len(pairs) > 0:
            self.strong_hole = True

        combined_allocation = ordered_singles + pairs # strongest hands at end

        for i in range(NUM_BOARDS):
            hand = [combined_allocation[2*i], combined_allocation[2*i + 1]]
            self.allocations[i] = hand


    def assign_holes(self, hole_cards):

        holes_and_strengths = [] # keep track of holes and their strengths

        for hole in hole_cards:
            strength = self.calculate_strength(hole, self.MONTE_CARLO_ITERS) # use our monte carlo sim!
            holes_and_strengths.append((hole, strength))
        
        holes_and_strengths = sorted(holes_and_strengths, key=lambda x: x[1]) # sort them by strength

        if random.random() < 0.15: # swap strongest with second, makes our strategy non-deterministic! TODO calculate Nash?
            temp = holes_and_strengths[2]
            holes_and_strengths[2] = holes_and_strengths[1]
            holes_and_strengths[1] = temp
        
        if random.random() < 0.15: # swap second with last, makes us even more random
            temp = holes_and_strengths[1]
            holes_and_strengths[1] = holes_and_strengths[0]
            holes_and_strengths[0] = temp
        
        for i in range(NUM_BOARDS): # we have our final board allocations!
            self.allocations[i] = holes_and_strengths[i][0]
            self.hole_strengths[i] = holes_and_strengths[i][1]


    def handle_new_round(self, game_state, round_state, active):
        '''
        Called when a new round starts. Called NUM_ROUNDS times.

        Arguments:
        game_state: the GameState object.
        round_state: the RoundState object.
        active: your player's index.

        Returns:
        Nothing.
        '''
        my_bankroll = game_state.bankroll  # the total number of chips you've gained or lost from the beginning of the game to the start of this round
        opp_bankroll = game_state.opp_bankroll # ^but for your opponent
        game_clock = game_state.game_clock  # the total number of seconds your bot has left to play this game
        round_num = game_state.round_num  # the round number from 1 to NUM_ROUNDS
        my_cards = round_state.hands[active]  # your six cards at teh start of the round
        big_blind = bool(active)  # True if you are the big blind
        
        allocated_holes = self.allocate_cards(my_cards)
        self.allocate_cards(my_cards)

    def handle_round_over(self, game_state, terminal_state, active):
        '''
        Called when a round ends. Called NUM_ROUNDS times.

        Arguments:
        game_state: the GameState object.
        terminal_state: the TerminalState object.
        active: your player's index.

        Returns:
        Nothing.
        '''
        my_delta = terminal_state.deltas[active]  # your bankroll change from this round
        opp_delta = terminal_state.deltas[1-active] # your opponent's bankroll change from this round 
        previous_state = terminal_state.previous_state  # RoundState before payoffs
        street = previous_state.street  # 0, 3, 4, or 5 representing when this round ended
        for terminal_board_state in previous_state.board_states:
            previous_board_state = terminal_board_state.previous_state
            my_cards = previous_board_state.hands[active]  # your cards
            opp_cards = previous_board_state.hands[1-active]  # opponent's cards or [] if not revealed

        self.allocations = [[], [], []]
        self.strong_hole = False

        game_clock = game_state.game_clock # check how much time we have remaining at the end of a game
        round_num = game_state.round_num # Monte Carlo takes a lot of time, we use this to adjust!
        if round_num == NUM_ROUNDS:
            print(game_clock)

    def get_actions(self, game_state, round_state, active):
        '''
        Where the magic happens - your code should implement this function.
        Called any time the engine needs a triplet of actions from your bot.

        Arguments:
        game_state: the GameState object.
        round_state: the RoundState object.
        active: your player's index.

        Returns:
        Your actions.
        '''
        legal_actions = round_state.legal_actions()  # the actions you are allowed to take
        street = round_state.street  # 0, 3, 4, or 5 representing pre-flop, flop, turn, or river respectively
        my_cards = round_state.hands[active]  # your cards across all boards
        board_cards = [board_state.deck if isinstance(board_state, BoardState) else board_state.previous_state.deck for board_state in round_state.board_states] # the board cards
        my_pips = [board_state.pips[active] if isinstance(board_state, BoardState) else 0 for board_state in round_state.board_states] # the number of chips you have contributed to the pot on each board this round of betting
        opp_pips = [board_state.pips[1-active] if isinstance(board_state, BoardState) else 0 for board_state in round_state.board_states] # the number of chips your opponent has contributed to the pot on each board this round of betting
        continue_cost = [opp_pips[i] - my_pips[i] for i in range(NUM_BOARDS)] #the number of chips needed to stay in each board's pot
        my_stack = round_state.stacks[active]  # the number of chips you have remaining
        opp_stack = round_state.stacks[1-active]  # the number of chips your opponent has remaining
        stacks = [my_stack, opp_stack]
        net_upper_raise_bound = round_state.raise_bounds()[1] # max raise across 3 boards
        net_cost = 0 # keep track of the net additional amount you are spending across boards this round
        

        my_actions = [None] * NUM_BOARDS # initializing [None, None, None]
        for i in range(NUM_BOARDS):
            if AssignAction in legal_actions[i]:
                cards = self.allocations[i] # assign our cards that we made earlier
                my_actions[i] = AssignAction(cards) # add to our actions

            elif isinstance(round_state.board_states[i], TerminalState): #make sure the game isn't over at this board
                my_actions[i] = CheckAction() #check if it is
            
            else: #do we add more resources?
                board_cont_cost = continue_cost[i] #we need to pay this to keep playing
                board_total = round_state.board_states[i].pot #amount before we started betting
                pot_total = my_pips[i] + opp_pips[i] + board_total #total money in the pot right now
                min_raise, max_raise = round_state.board_states[i].raise_bounds(active, round_state.stacks)
                strength = self.hole_strengths[i]

                if street < 3: #pre-flop
                    raise_ammount = int(my_pips[i] + board_cont_cost + 0.4 * (pot_total + board_cont_cost)) #play a little conservatively pre-flop
                else:
                    raise_ammount = int(my_pips[i] + board_cont_cost + 0.75 * (pot_total + board_cont_cost)) #raise the stakes deeper into the game
                
                raise_ammount = max([min_raise, raise_ammount]) #make sure we have a valid raise
                raise_ammount = min([max_raise, raise_ammount])

                raise_cost = raise_ammount - my_pips[i] #how much it costs to make that raise

                if RaiseAction in legal_actions[i] and (raise_cost <= my_stack - net_cost): #raise if we can and if we can afford it
                    commit_action = RaiseAction(raise_ammount)
                    commit_cost = raise_cost
                
                elif CallAction in legal_actions[i] and (board_cont_cost <= my_stack - net_cost): #call if we can afford it!
                    commit_action = CallAction()
                    commit_cost = board_cont_cost #the cost to call is board_cont_cost
                
                elif CheckAction in legal_actions[i]: #try to check if we can
                    commit_action = CheckAction()
                    commit_cost = 0
                
                else: #we have to fold 
                    commit_action = FoldAction()
                    commit_cost = 0


                if board_cont_cost > 0: #our opp raised!!! we must respond

                    if board_cont_cost > 5: #<--- parameters to tweak. 
                        _INTIMIDATION = 0.15
                        strength = max([0, strength - _INTIMIDATION]) #if our opp raises a lot, be cautious!
                    

                    pot_odds = board_cont_cost / (pot_total + board_cont_cost)

                    if strength >= pot_odds: #Positive Expected Value!! at least call!!

                        if strength > 0.5 and random.random() < strength: #raise sometimes, more likely if our hand is strong
                            my_actions[i] = commit_action
                            net_cost += commit_cost
                        
                        else: # try to call if we don't raise
                            if (board_cont_cost <= my_stack - net_cost): #we call because we can afford it and it's +EV
                                my_actions[i] = CallAction()
                                net_cost += board_cont_cost
                                
                            else: #we can't afford to call :(  should have managed our stack better
                                my_actions[i] = FoldAction()
                                net_cost += 0
                    
                    else: #Negative Expected Value!!! FOLD!!!
                        my_actions[i] = FoldAction()
                        net_cost += 0
                
                else: #board_cont_cost == 0, we control the action

                    if random.random() < strength: #raise sometimes, more likely if our hand is strong
                        my_actions[i] = commit_action
                        net_cost += commit_cost

                    else: #just check otherwise
                        my_actions[i] = CheckAction()
                        net_cost += 0

        return my_actions


if __name__ == '__main__':
    run_bot(Player(), parse_args())
