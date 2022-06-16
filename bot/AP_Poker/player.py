'''
AP Poker, written in Python. Graduated to GRE Poker!
'''
from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction, AssignAction
from skeleton.states import GameState, TerminalState, RoundState, BoardState
from skeleton.states import NUM_ROUNDS, STARTING_STACK, BIG_BLIND, SMALL_BLIND, NUM_BOARDS
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot

import eval7
import random
import pandas as pd
import math

NUMS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K']
SUITS = ['s', 'c', 'd', 'h']
FULL_DECK = []

for i in range(13):
    for j in range(4):
        FULL_DECK.append(NUMS[i] + SUITS[j])

_MONTE_CARLO_ITERS = 400

_INTIMIDATION_THRESHOLD = 0
# _RAISE_MIN_STR = {'pre': 0.5949558282767977, 'post': 0.7589461055235294}
# _CALL_MIN_STR = {'pre': 0.553931153868574, 'post': 0.6767204003287182}
# _RAISE_MIN_STR = {'pre': 0.596488763163911, 'post': 0.7546472617100061}
# _CALL_MIN_STR = {'pre': 0.5562149565966004, 'post': 0.6781369912929057}
# _RAISE_MIN_STR = {'pre': 0.5970934861998453, 'post': 0.7571706199293162}
# _CALL_MIN_STR = {'pre': 0.5566325929675454, 'post': 0.6809086045589033}
# _RAISE_MIN_STR = {'pre': 0.604340090276017, 'post': 0.7683097752355128}
# _CALL_MIN_STR = {'pre': 0.5682854405323807, 'post': 0.6721926278636581}
# _RAISE_MIN_STR = {'pre': 0.6039772008929409, 'post': 0.7634834241121107}
# _CALL_MIN_STR = {'pre': 0.5806197320675985, 'post': 0.6839378722535923}
# _RAISE_VALUES = {'exp': 1.821986223132889, 'const': 12.79352430248694}
# _RAISE_MIN_STR = {'pre': 0.6172871835960861, 'post': 0.7406420960264349}
# _CALL_MIN_STR = {'pre': 0.5836431975238623, 'post': 0.6967741298575294}
# _RAISE_VALUES = {'exp': 1.8537556711228251, 'const': 11.387321216037845}
# _RAISE_MIN_STR = {'pre': 0.6195379208659013, 'post': 0.712232703167777}
# _CALL_MIN_STR = {'pre': 0.5736004167899637, 'post': 0.6372627070980238}
# _RAISE_VALUES = {'exp': 1.8686303800527027, 'const': 12.20395612510144}
_RAISE_MIN_STR = {'pre': 0.6066179515462299, 'post': 0.7212909509127321}
_CALL_MIN_STR = {'pre': 0.5570778707878955, 'post': 0.6207629881906793}
_RAISE_VALUES = {'exp': 1.8301191486578343, 'const': 14.439631715170798}


RANK_DICT = {'2':2, '3':3, '4':4, '5':5, '6':6, '7':7, '8':8, '9':9, 'T':10, 'J':11, 'Q':12, 'K':13, 'A':14}

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
        self.board_allocations = [[], [], []] # keep track of our allocations at round start
        self.hole_strengths = [0, 0, 0] # better representation of our hole strengths per round (win probability!)
        # self.parameters = {'pr':0, 'pc':1, 'pf':0}

        self.total_payoffs = 0
        self.mutated = False
        self.draise_pre = 0
        self.draise_post = 0
        self.dcall_pre = 0
        self.dcall_post = 0
        self.draise_exp = 0
        self.draise_const = 0

        # make sure this df isn't too big!! Loading data all at once might be slow if you did more computations!
        calculated_df = pd.read_csv('hole_strengths.csv') # the values we computed offline, this df is slow to search through though
        holes = calculated_df.Holes # the columns of our spreadsheet
        strengths = calculated_df.Strengths
        self.starting_strengths = dict(zip(holes, strengths)) # convert to a dictionary, O(1) lookup time!


    def rank_to_numeric(self, rank):
        '''
        Method that converts our given rank as a string
        into an integer ranking

        rank: str - one of 'A, K, Q, J, T, 9, 8, 7, 6, 5, 4, 3, 2'
        '''

        return RANK_DICT[rank]


    def sort_cards_by_rank(self, cards):
        '''
        Method that takes in a list of cards in the engine's format
        and sorts them by rank order

        cards: list - a list of card strings in the engine's format (Kd, As, Th, 7d, etc.)
        '''
        return sorted(cards, reverse=True, key=lambda x: self.rank_to_numeric(x[0])) # we want it in descending order


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
        for k in range(3):
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

            self.board_allocations[2-k] = temp_cards
            self.hole_strengths[2-k] = max_strength_hole
            my_cards.remove(temp_cards[0]) 
            my_cards.remove(temp_cards[1])
            

    def public_eval(self, private, public, street, iters):
        """
        evaluate current combined hand with hole + community cards, then calculate pot odds by running through all other cards

        params: tuple of private_cards, tuple of public_cards
        """

        _PUB = 5 - street # number of public cards to be drawn (turn/river)
        _OPP = 2
        score = 0

        remaining_cards = set(FULL_DECK)
        remaining_cards -= set(private)
        remaining_cards -= set(public)
        
        for _ in range(iters):
            draw = random.sample(remaining_cards, _OPP + _PUB) # pull 2 cards for opp_hole, and 5 - street cards for hidden_public (depending on turn and river)
            opp_hole = draw[:_OPP]
            hidden_public = draw[_OPP:]

            my_strength = eval7.evaluate([eval7.Card(card) for card in tuple(private + public + hidden_public)])
            opp_strength = eval7.evaluate([eval7.Card(card) for card in tuple(opp_hole + public + hidden_public)])

            if my_strength > opp_strength:
                score += 2
            elif my_strength == opp_strength:
                score += 1
            else:
                pass

        return score/(2 * iters)


    # def cfr(self, history, p0, p1):
    #     int plays = history.length();
    #     int player = plays % 2;
    #     int opponent = 1 - player;
    #     ⟨Return payoff for terminal states⟩
    #     String infoSet = cards[player] + history;
    #     ⟨Get information set node or create it if nonexistant⟩
    #     ⟨For each action, recursively call cfr with additional history and probability⟩ ⟨For each action, compute and accumulate counterfactual regret⟩
    #         return nodeUtil;


    # def fake_cfr(self, game_state, round_state, active): # TODO change NUM_ROUNDS while training?
    #     '''
    #     Simple A/B testing; record values of whichever does better, then take average 
    #     '''

        
    #     if game_state.round_num == NUM_ROUNDS:
    #         print(parameters)
    
    def mutate(self, game_state, terminal_state, active):
        my_delta = terminal_state.deltas[active] # your bankroll change from this round
        round_num = game_state.round_num
        
        self.total_payoffs += my_delta
        
        mutate_iters = 5

        if round_num % mutate_iters == 0:
            # self.adjust_iters(game_state)
            if self.total_payoffs < 6 * mutate_iters:
                if not self.mutated:
                    print('went extinct :( new mutation...')
                    self.mutated = True

                    self.draise_pre = (random.random() * 0.05 - 0.025)/math.sqrt(round_num / mutate_iters)
                    self.draise_post = (random.random() * 0.05 - 0.025)/math.sqrt(round_num / mutate_iters)
                    self.dcall_pre = (random.random() * 0.05 - 0.025)/math.sqrt(round_num / mutate_iters)
                    self.dcall_post = (random.random() * 0.05 - 0.025)/math.sqrt(round_num / mutate_iters)
                    self.draise_exp = (random.random() * 0.1 - 0.05)/math.sqrt(round_num / mutate_iters)
                    self.draise_const = (random.random() * 4 - 2)/math.sqrt(round_num / mutate_iters)


                    _RAISE_MIN_STR['pre'] += self.draise_pre
                    _RAISE_MIN_STR['post'] += self.draise_post
                    _CALL_MIN_STR['pre'] += self.dcall_pre
                    _CALL_MIN_STR['post'] += self.dcall_post
                    _RAISE_VALUES['exp'] += self.draise_exp
                    _RAISE_VALUES['const'] += self.draise_const

                    print('_RAISE_MIN_STR =', _RAISE_MIN_STR)
                    print('_CALL_MIN_STR =', _CALL_MIN_STR)
                    print('_RAISE_VALUES =', _RAISE_VALUES)

                else:
                    print('went extinct again :( flipping mutation...')
                    self.mutated = False

                    _RAISE_MIN_STR['pre'] -= self.draise_pre
                    _RAISE_MIN_STR['post'] -= self.draise_post
                    _CALL_MIN_STR['pre'] -= self.dcall_pre
                    _CALL_MIN_STR['post'] -= self.dcall_post
                    _RAISE_VALUES['exp'] -= self.draise_exp
                    _RAISE_VALUES['const'] -= self.draise_const

                    print('_RAISE_MIN_STR =', _RAISE_MIN_STR)
                    print('_CALL_MIN_STR =', _CALL_MIN_STR)
                    print('_RAISE_VALUES =', _RAISE_VALUES)
            
            elif self.total_payoffs == 6 * mutate_iters:
                print('tie?!?!?!')

            else:
                print('did well :)')

                # if self.mutated: # repeating good mutation until it passes maximum
                #     print('mutating further...')

                #     _RAISE_MIN_STR['pre'] += self.draise_pre
                #     _RAISE_MIN_STR['post'] += self.draise_post
                #     _CALL_MIN_STR['pre'] += self.dcall_pre
                #     _CALL_MIN_STR['post'] += self.dcall_post

                #     print('_RAISE_MIN_STR =', _RAISE_MIN_STR)
                #     print('_CALL_MIN_STR =', _CALL_MIN_STR)

                # else: # TODO comment this loop out on final server; if good, don't mutate
                #     print('trying new mutation...')

                    # self.draise_pre = (random.random() * 0.05 - 0.025)/math.sqrt(round_num / mutate_iters)
                    # self.draise_post = (random.random() * 0.05 - 0.025)/math.sqrt(round_num / mutate_iters)
                    # self.dcall_pre = (random.random() * 0.05 - 0.025)/math.sqrt(round_num / mutate_iters)
                    # self.dcall_post = (random.random() * 0.05 - 0.025)/math.sqrt(round_num / mutate_iters)

                #     _RAISE_MIN_STR['pre'] += self.draise_pre
                #     _RAISE_MIN_STR['post'] += self.draise_post
                #     _CALL_MIN_STR['pre'] += self.dcall_pre
                #     _CALL_MIN_STR['post'] += self.dcall_post

                #     print('_RAISE_MIN_STR =', _RAISE_MIN_STR)
                #     print('_CALL_MIN_STR =', _CALL_MIN_STR)

                # self.mutated = True

                self.mutated = False

            self.total_payoffs = 0 # reset accumulated payoff
            


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
        my_bankroll = game_state.bankroll # the total number of chips you've gained or lost from the beginning of the game to the start of this round
        opp_bankroll = game_state.opp_bankroll # ^but for your opponent
        game_clock = game_state.game_clock # the total number of seconds your bot has left to play this game
        round_num = game_state.round_num # the round number from 1 to NUM_ROUNDS
        my_cards = round_state.hands[active] # your six cards at the start of the round
        big_blind = bool(active) # True if you are the big blind

        self.allocate_cards(my_cards)

    
    def adjust_iters(self, game_state): # TODO fix _MONTE_CARLO_ITERS
        game_clock = game_state.game_clock
        round_num = game_state.round_num

        rounds_frac = round_num/NUM_ROUNDS
        time_frac = (30 - game_clock)/30

        _MONTE_CARLO_ITERS = int(_MONTE_CARLO_ITERS * rounds_frac/time_frac * 0.9)


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
        my_delta = terminal_state.deltas[active] # your bankroll change from this round
        opp_delta = terminal_state.deltas[1-active] # your opponent's bankroll change from this round 
        previous_state = terminal_state.previous_state # RoundState before payoffs
        street = previous_state.street # 0, 3, 4, or 5 representing when this round ended
        for terminal_board_state in previous_state.board_states:
            previous_board_state = terminal_board_state.previous_state
            my_cards = previous_board_state.hands[active] # your cards
            opp_cards = previous_board_state.hands[1-active] # opponent's cards or [] if not revealed
        
        self.board_allocations = [[], [], []] # reset our variables at the end of every round!
        self.hole_strengths = [0, 0, 0]
        self.last_seen_street = 0

        game_clock = game_state.game_clock # check how much time we have remaining at the end of a game
        round_num = game_state.round_num # Monte Carlo takes a lot of time, we use this to adjust!

        self.mutate(game_state, terminal_state, active)

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
        legal_actions = round_state.legal_actions() # the actions you are allowed to take
        street = round_state.street # 0, 3, 4, or 5 representing pre-flop, flop, turn, or river respectively
        my_cards = round_state.hands[active] # your cards across all boards
        board_cards = [board_state.deck if isinstance(board_state, BoardState) else board_state.previous_state.deck for board_state in round_state.board_states] # the board cards
        my_pips = [board_state.pips[active] if isinstance(board_state, BoardState) else 0 for board_state in round_state.board_states] # the number of chips you have contributed to the pot on each board this round of betting
        opp_pips = [board_state.pips[1-active] if isinstance(board_state, BoardState) else 0 for board_state in round_state.board_states] # the number of chips your opponent has contributed to the pot on each board this round of betting
        continue_cost = [opp_pips[i] - my_pips[i] for i in range(NUM_BOARDS)] # the number of chips needed to stay in each board's pot
        my_stack = round_state.stacks[active] # the number of chips you have remaining
        opp_stack = round_state.stacks[1-active] # the number of chips your opponent has remaining
        stacks = [my_stack, opp_stack]
        net_upper_raise_bound = round_state.raise_bounds()[1] # max raise across 3 boards
        net_cost = 0 # keep track of the net additional amount you are spending across boards this round

        my_actions = [None] * NUM_BOARDS
        for i in range(NUM_BOARDS):
            cards = self.board_allocations[i] # assign our cards that we made earlier
            if AssignAction in legal_actions[i]:
                my_actions[i] = AssignAction(cards) # add to our actions
                
            elif isinstance(round_state.board_states[i], TerminalState): # make sure the game isn't over at this board
                my_actions[i] = CheckAction() # check if it is
            
            else: # do we add more resources?
                board_cont_cost = continue_cost[i] # we need to pay this to keep playing
                board_total = round_state.board_states[i].pot # amount before we started betting
                pot_total = my_pips[i] + opp_pips[i] + board_total # total money in the pot right now
                min_raise, max_raise = round_state.board_states[i].raise_bounds(active, round_state.stacks)

                if street < 3: # pre-flop
                    state_str = 'pre'
                    strength = self.hole_strengths[i] # pull from hole_strengths.csv
                    if self.starting_strengths[self.hole_list_to_key(cards)] > _RAISE_MIN_STR[state_str]:
                        raise_amount = int(my_pips[i] + board_cont_cost + (strength - 0.5) * 10) # play conservative pre-flop
                    else: 
                        raise_amount = 0 # min_raise
                else:
                    state_str = 'post'
                    strength = self.public_eval(cards, board_cards[i][:street], street, _MONTE_CARLO_ITERS) # run Monte Carlo sims to estimate str of hand
                    # print('hole:', cards)
                    # print('pub:', board_cards[i][:street])
                    # print('strength:', strength)
                    if strength > _RAISE_MIN_STR[state_str]:
                        # raise_amount = int(my_pips[i] + board_cont_cost + street/2 * math.sqrt(strength - 0.5) * 50) # raise the stakes deeper into the game
                        # raise_amount = int(my_pips[i] + board_cont_cost + street * math.exp(6.1 * (strength - 0.321875)) - 8.8)
                        raise_amount = int(my_pips[i] + board_cont_cost + street**2 * math.exp(_RAISE_VALUES['exp'] * (strength - 0.321875)) - _RAISE_VALUES['const'])
                    else:
                        raise_amount = 0 # min_raise

                # make sure we have a valid raise
                raise_amount = max(min_raise, raise_amount)
                raise_amount = min(max_raise, raise_amount)

                raise_cost = raise_amount - my_pips[i] # how much it costs to make that raise

                if RaiseAction in legal_actions[i] and (raise_cost <= my_stack - net_cost) and raise_cost != 0: # raise if we can and if we can afford it and if it's legal
                    commit_action = RaiseAction(raise_amount)
                    commit_cost = raise_cost
                
                elif CallAction in legal_actions[i] and (board_cont_cost <= my_stack - net_cost): # call if we can afford it!
                    commit_action = CallAction()
                    commit_cost = board_cont_cost # the cost to call is board_cont_cost
                
                elif CheckAction in legal_actions[i]: # try to check if we can
                    commit_action = CheckAction()
                    commit_cost = 0
                
                else: # we have to fold 
                    commit_action = FoldAction()
                    commit_cost = 0

                if board_cont_cost > 0: # our opp raised!!! we must respond
                    preintimidation_strength = strength # TODO use this or no? 
                    if board_cont_cost > _INTIMIDATION_THRESHOLD: # <--- parameters to tweak. 
                        if street == 0 and board_cont_cost > 20: # hardcode to counter stupidly big bluff preflop
                            pass
                        else:
                            # * math.sqrt(9 - street)/2 
                            # * math.sqrt(20 + street)/5
                            intimidation = 0.05 * math.sqrt(board_cont_cost - _INTIMIDATION_THRESHOLD) * math.sqrt(strength)
                            strength = max(0, strength - intimidation) # if our opp raises a lot, be cautious!

                    pot_odds = board_cont_cost / (pot_total + board_cont_cost)

                    if strength >= pot_odds: # Positive Expected Value!! at least call!!
                        if random.random() < 1.4 * strength and preintimidation_strength > _RAISE_MIN_STR[state_str]: # raise sometimes, more likely if our hand is strong
                            my_actions[i] = commit_action
                            net_cost += commit_cost
                        
                        elif (math.sqrt(board_cont_cost - _INTIMIDATION_THRESHOLD) < 6 and preintimidation_strength > _CALL_MIN_STR[state_str]) or preintimidation_strength > _RAISE_MIN_STR[state_str]: # try to call if we don't raise
                            if (board_cont_cost <= my_stack - net_cost): # we call because we can afford it and it's +EV
                                my_actions[i] = CallAction()
                                net_cost += board_cont_cost
                                
                            else: # we can't afford to call :( should have managed our stack better
                                # my_actions[i] = RaiseAction(my_stack - net_cost) # all-in, might want to scale down if other boards are better?
                                # net_cost += my_stack - net_cost
                                my_actions[i] = FoldAction() # TODO don't fold if you want to all-in?
                                net_cost += 0

                        else:
                            my_actions[i] = FoldAction()
                            net_cost += 0
                    
                    else: # Negative Expected Value!!! FOLD!!!
                        my_actions[i] = FoldAction()
                        net_cost += 0
                
                else: # board_cont_cost == 0, we control the action
                    if random.random() < 1.4 * strength and strength > _RAISE_MIN_STR[state_str]: # raise sometimes, more likely if our hand is strong
                        my_actions[i] = commit_action
                        net_cost += commit_cost

                    else: # just check otherwise
                        my_actions[i] = CheckAction()
                        net_cost += 0

        return my_actions


if __name__ == '__main__':
    run_bot(Player(), parse_args())