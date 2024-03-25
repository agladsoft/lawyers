import itertools as itt
import datetime as dt
import logging
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass
import heapq
import re
import numpy as np
import os
import string


import fuzzywuzzy.fuzz
from fuzzywuzzy import process


logger = logging.getLogger(__name__)


def init_my_logging():
    """
    Configuring logging for a SON-like appearance when running locally
    """
    logger.setLevel(logging.DEBUG)
    log_file_name = os.path.splitext(os.path.realpath(__file__))[0] + '.log'
    handler = RotatingFileHandler(log_file_name, maxBytes=1.5 * pow(1024, 2), backupCount=3)
    log_format = "%(asctime)-15s [{}:%(name)s:%(lineno)s:%(funcName)s:%(levelname)s] %(message)s".format(os.getpid())
    handler.setLevel(logging.DEBUG)
    try:
        from colorlog import ColoredFormatter
        formatter = ColoredFormatter(log_format)
    except ImportError:
        formatter = logging.Formatter(log_format)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)


init_my_logging()


class Paragraph(object):
    def __init__(self, symbols, position, nbrs, match_paragraph=None):
        self.symbols = self._clean_symbols(symbols)
        self.symbols_count = len(self.symbols)
        self.global_position = position
        self.token_borders = self._get_cleaned_token_borders()
        self.tokens, self.token_start_end = self._get_tokens(2)
        self.tokens_count = len(self.tokens)
        self.prev = nbrs[0]
        self.next = nbrs[1]
        self.match_paragraph = match_paragraph

    def __repr__(self):
        symbols_a = self.symbols[:min(len(self.symbols), 15)]
        symbols_z = self.symbols[min(len(self.symbols), 15):]
        return f'{self.__class__.__name__}(global_position={self.global_position}, symbols=({symbols_a}...{symbols_z}))'

    def _clean_symbols(self, symbols):
        new_symbols = re.sub(r"\s{2,}", " ", symbols)
        new_symbols += " "
        new_symbols = re.sub(r"\s+$", "\n", new_symbols)
        return new_symbols

    def _get_cleaned_token_borders(self):
        token_borders = list(self._get_token_borders())
        # token_borders2 = list(self._clean_token_borders(token_borders))
        return token_borders

    def _get_token_borders(self):
        splitter = " "
        j = 0
        yield 0
        while j != -1:
            j = self.symbols.find(splitter, j + 4)
            if j == -1:
                yield len(self.symbols)
            else:
                yield j

    def _clean_token_borders(self, token_borders):
        for a, b in itt.pairwise(token_borders):
            if b - a > 2 or a == 0:
                yield a
        yield b

    def _get_tokens(self, words_count):
        tokens = []
        tokens_start_end = []
        for i in range(len(self.token_borders)-words_count):
            start = self.token_borders[i]
            end = self.token_borders[i+words_count]
            token = self.symbols[start:end]
            tokens.append(token)
            tokens_start_end.append((start, end))
        if not tokens:
            tokens.append(self.symbols)
            tokens_start_end.append((self.token_borders[0], self.token_borders[-1]))
        return tokens, tokens_start_end

    def get_token_pos_in_text(self, token):
        start = self.symbols._find_right_tokens(token)
        end = start + len(token)
        return start, end




def paragraph_factory(text):
    """Creates dict[Paragraph] with absolute start position of every paragraph as dict key"""
    prev_p = None
    global_position = 0
    paragraphs = dict()
    text += "\n"  # add empty paragraph because we work with start positions of paragraphs
    for line in text:
        current_p = Paragraph(line, position=global_position, nbrs=(prev_p, None))
        paragraphs[global_position] = current_p
        global_position += len(line)
        if prev_p:
            prev_p.next = current_p
        prev_p = current_p
    return paragraphs


class ParagraphHandler(object):
    def __init__(self, paragraphs= Paragraph):
        self.paragraphs = paragraphs

    def is_paragragrapth_with_position_exists(self, pos):
        result = pos in self.paragraphs.keys()
        return result

    def get_position_before(self, pos):
        position_before = max((p for p in self.paragraphs.keys() if p < pos))
        return position_before

    def get_position_after(self, pos):
        position_after = min((p for p in self.paragraphs.keys() if p > pos))
        return position_after

    def __repr__(self):
        return f'{self.__class__.__name__}'

    def spawn_child(self, pos_spawn):
        # TODO: pos_spawn should contain paragrapth global position + token position within parahraph
        logger.debug(f'{self} will spawn child at pos_spawn={pos_spawn}')
        if self.is_paragragrapth_with_position_exists(pos_spawn):
            assert 'already exist'

        pos_before = self.get_position_before(pos_spawn)
        current_p = self.paragraphs[pos_before]
        logger.debug(f'pos_before={pos_before}, current_p={current_p}')

        slice = pos_spawn-pos_before+1
        parent_symbols = current_p.symbols[:slice] + '\n'
        parent = Paragraph(symbols=parent_symbols, position=current_p.global_position,
                           nbrs=(current_p.prev, None))
        logger.debug(f'parent is {parent}')

        child_symbols = self.paragraphs[pos_before].symbols[slice:]
        child = Paragraph(symbols=child_symbols, position=pos_spawn,
                          nbrs=(parent, current_p.next))
        logger.debug(f'child is {child}')
        parent.next = child

        self.paragraphs.pop(pos_before)
        self.paragraphs[pos_before] = parent
        self.paragraphs[pos_spawn] = child
        self.paragraphs = dict(sorted(self.paragraphs.items()))
        return parent, child

class ChapterSide(object):
    """One side of chapter"""

    def __init__(self, paragraphs: dict, start_id: int, end_id: int):
        self.paragraphs = paragraphs
        self.start_id = start_id
        self.end_id = end_id

    def __repr__(self):
        return f'{self.__class__.__name__}(start_id={self.start_id}, end_id={self.end_id})'

    def spawn_child(self, spawn_global_position: int, spawn_local_position: int = 0):
        logger.debug(f'{self} will spawn child...')
        spawn_sum_position = spawn_global_position + spawn_local_position
        logger.debug(f'spawn_global_position={spawn_global_position}, spawn_local_position={spawn_local_position} '
                     f'spawn_sum_position={spawn_sum_position}')
        paragraph_handler = ParagraphHandler(self.paragraphs)
        if not paragraph_handler.is_paragragrapth_with_position_exists(spawn_sum_position):
            paragraph_handler.spawn_child(spawn_sum_position)
        parent = ChapterSide(paragraphs=self.paragraphs, start_id=self.start_id,
                             end_id=paragraph_handler.get_position_before(spawn_sum_position))

        # end_id = paragraph_handler.get_position_after(spawn_global_position)
        # end_id = paragraph_handler.get_position_before(end_id)
        child = ChapterSide(paragraphs=self.paragraphs, start_id=spawn_sum_position, end_id=max(spawn_sum_position, self.end_id))

        return parent, child

@dataclass
class FoundRightToken:
    text: str
    rate: int
    paragraph_id: int
    relative_pos: float


class BorderTokenMatch(object):
    def __init__(self, left_token: str, right_tokens: dict):
        self.left_token = left_token
        self.right_tokens = right_tokens
        self.right_tokens_min_id = min(self.right_tokens.keys())
        self.right_tokens_max_id = max(self.right_tokens.keys())
        self.found_right_tokens = list(self._find_right_tokens())

    def __repr__(self):
        return str(dict(
            left_token=self.left_token,
            count_right_tokens=len(self.right_tokens),
            right_tokens_min_id=self.right_tokens_min_id,
            right_tokens_max_id=self.right_tokens_max_id,
            found_right_tokens=self.found_right_tokens
        ))

    def _find_right_tokens(self):
        found_right_tokens_and_rates = process.extract(query=self.left_token,
                                                       choices=self.right_tokens.values(),
                                                       scorer=fuzzywuzzy.fuzz.ratio,
                                                       limit=3)
        already_found_ids = set()
        for found_right_token, found_right_token_rate in found_right_tokens_and_rates:
            paragraph_id = next((k for k, v in self.right_tokens.items()
                                 if v == found_right_token and k not in already_found_ids), (None, None))
            already_found_ids.add(paragraph_id)
            yield FoundRightToken(text=found_right_token,
                                  rate=found_right_token_rate,
                                  paragraph_id=paragraph_id,
                                  relative_pos=paragraph_id/self.right_tokens_max_id)


class BorderMatch(object):
    def __init__(self, left_bstart_token, left_bend_token, left_border_pid,
                 right_bstart_tokens, right_bend_tokens, right_chapter):
        self.left_bstart_token = left_bstart_token
        self.left_bend_token = left_bend_token
        self.left_border_pid = left_border_pid
        self.right_bstart_tokens = right_bstart_tokens
        self.right_bend_tokens = right_bend_tokens
        self.right_chapter = right_chapter
        # logger.debug(f"left_bstart_token='{left_bstart_token}', count(right_bstart_tokens)={len(right_bstart_tokens)}")
        self.bstart_token_match = BorderTokenMatch(left_bstart_token, right_bstart_tokens)
        # logger.debug(f"bstart_token_match='{self.bstart_token_match}")
        # logger.debug(f"left_bstart_token='{left_bend_token}', count(right_bstart_tokens)={len(right_bend_tokens)}")
        self.bend_token_match = BorderTokenMatch(left_bend_token, right_bend_tokens)
        # logger.debug(f"bend_token_match='{self.bend_token_match}")

        self.best_bstart_right_token, \
        self.best_bend_right_token, \
        self.tokens_rate, \
        self.best_char_distance = self._get_best_found_bend_bstart_tokens_and_best_char_distance()
        a = 1
        if not self.best_bend_right_token:
            logger.debug(f"best_bend_right_token is {self.best_bend_right_token}, no good match found?")

        # self.tokens_rate = self._get_tokens_rate()

        self.border_rate = self.tokens_rate / 10 + self.best_char_distance
        a = 1

    def __repr__(self):
        return str(dict(left_bstart_token=self.left_bstart_token,
                        left_bend_token=self.left_bend_token,
                        best_bstart_right_token=self.best_bstart_right_token,
                        best_bend_right_token=self.best_bend_right_token,
                        tokens_rate=self.tokens_rate,
                        best_char_distance=self.best_char_distance,
                        border_rate=self.border_rate
        ))

    def __lt__(self, other):
        return self.border_rate < other.border_rate

    @staticmethod
    def _get_mse_of_found_right_tokens(bs: FoundRightToken, be: FoundRightToken):
        y_true = [100, 100]  # Y_true = Y (original values)
        # Calculated values
        y_pred = [bs.rate, be.rate]  # Y_pred = Y'
        # Mean Squared Error
        mse = np.square(np.subtract(y_true, y_pred)).mean()
        return mse

    def _get_best_found_bend_bstart_tokens_and_best_char_distance(self):
        best_bs = None
        best_be = None
        best_mse = 99999999
        best_char_distance = 99999999
        for bs, be in itt.product(self.bstart_token_match.found_right_tokens,
                                  self.bend_token_match.found_right_tokens):
            char_distance = be.paragraph_id - \
                            bs.paragraph_id - \
                            self.right_chapter.paragraphs[bs.paragraph_id].symbols_count
            mse = self._get_mse_of_found_right_tokens(bs, be)

            if mse == 0.0 and 1 >= char_distance >= -1:
                best_bs, best_be, best_mse, best_char_distance = bs, be, mse, char_distance
                break

            if (char_distance >= -1) and (char_distance <= best_char_distance) and (mse < best_mse):
                best_bs, best_be, best_mse, best_char_distance,  = bs, be, mse, char_distance
        a = 1
        return best_bs, best_be, best_mse, best_char_distance


class BorderMatchByToken(BorderMatch):
    def _get_best_found_bend_bstart_tokens_and_best_char_distance(self):
        best_bs = None
        best_be = None
        best_mse = 99999999
        best_char_distance = 99999999
        for bs, be in itt.product(self.bstart_token_match.found_right_tokens,
                                  self.bend_token_match.found_right_tokens):
            char_distance = be.paragraph_id - \
                            bs.paragraph_id - \
                            len(bs.text)
            mse = self._get_mse_of_found_right_tokens(bs, be)

            if (char_distance >= 0) and (char_distance <= best_char_distance) and (mse < best_mse):
                best_bs, best_be, best_mse, best_char_distance,  = bs, be, mse, char_distance
        a = 1
        return best_bs, best_be, best_mse, best_char_distance


class BorderMatchByBestBorderEndToken(BorderMatchByToken):

    @staticmethod
    def _get_mse_of_found_right_tokens(bs: FoundRightToken, be: FoundRightToken):
        # bs_error = 100 - bs.rate
        be_error = 100 - be.rate
        # mse = min(bs_error, be_error)
        return be_error

    def _get_best_found_bend_bstart_tokens_and_best_char_distance(self):
        best_bs = None
        best_be = None
        best_mse = 99999999
        best_char_distance = 99999999
        for bs, be in itt.product(self.bstart_token_match.found_right_tokens,
                                  self.bend_token_match.found_right_tokens):
            char_distance = 0
            mse = self._get_mse_of_found_right_tokens(bs, be)

            if mse < best_mse:
                best_bs, best_be, best_mse, best_char_distance,  = bs, be, mse, char_distance
        a = 1
        return best_bs, best_be, best_mse, best_char_distance




class BorderMatchByBestBorderStartToken(BorderMatchByToken):

    @staticmethod
    def _get_mse_of_found_right_tokens(bs: FoundRightToken, be: FoundRightToken):
        bs_error = 100 - bs.rate
        # be_error = 100 - be.rate
        # mse = min(bs_error, be_error)
        return bs_error

    def _get_best_found_bend_bstart_tokens_and_best_char_distance(self):
        best_bs = None
        best_be = None
        best_mse = 99999999
        best_char_distance = 99999999
        for bs, be in itt.product(self.bstart_token_match.found_right_tokens,
                                  self.bend_token_match.found_right_tokens):
            char_distance = 0
            mse = self._get_mse_of_found_right_tokens(bs, be)

            if mse < best_mse:
                best_bs, best_be, best_mse, best_char_distance,  = bs, be, mse, char_distance
        a = 1
        nbr_be_paragraph_id = len(best_bs.text) + best_bs.paragraph_id
        nbr_be_text = self.right_bend_tokens[nbr_be_paragraph_id]
        enforced_best_be = FoundRightToken(text=nbr_be_text,
                                           rate=100,
                                           paragraph_id=nbr_be_paragraph_id,
                                           relative_pos=None)
        return best_bs, enforced_best_be, best_mse, best_char_distance



class MatchedChapter(object):
    """Chapter that match left and right side, check and spawn subchapter if possible"""
    def __init__(self, left_chapter: ChapterSide, right_chapter: ChapterSide, nbrs: tuple = (None, None),
                 born_border_match: float = None):
        self.left_chapter = left_chapter
        self.right_chapter = right_chapter
        self.se2_id = (left_chapter.start_id, left_chapter.end_id), (right_chapter.start_id, right_chapter.end_id)
        self.right_bstart_tokens = dict()
        self.right_bend_tokens = dict()
        self._get_right_tokens()
        self.border_matches_heap = self._fill_border_matches_heap()
        self.best_border_match = self.border_matches_heap[0] if self.border_matches_heap else None
        self.born_border_match = born_border_match
        self.born_datetime = dt.datetime.now()
        self.is_obsolete = False

        self.prev = nbrs[0]
        self.next = nbrs[1]

    def __repr__(self):
        return f'{self.__class__.__name__}(se2_id={self.se2_id}, is_obsolete={self.is_obsolete}, ' \
               f'prev={self.prev.se2_id if self.prev else None}, ' \
               f'next={self.next.se2_id if self.next else None})'

    def _get_right_tokens(self):
        """
        Fill right_bstart_tokens with tokens that may be in the start of the border - end of current paragraph.
        And right_bend_tokens with tokens that may be in the end of the border - start of next paragraph.
        """
        right_p = self.right_chapter.paragraphs[self.right_chapter.start_id]
        while right_p and right_p.global_position <= self.right_chapter.end_id:
            if right_p.global_position != self.right_chapter.end_id:
                self.right_bstart_tokens[right_p.global_position] = right_p.tokens[-1]
            if right_p.global_position != self.right_chapter.start_id:
                self.right_bend_tokens[right_p.global_position] = right_p.tokens[0]
            right_p = right_p.next

    def _fill_border_matches_heap(self):
        border_matches_heap = []
        left_p = self.left_chapter.paragraphs[self.left_chapter.start_id]
        while left_p.global_position < self.left_chapter.end_id:
            try:
                border_match = BorderMatch(left_bstart_token=left_p.tokens[-1],
                                           left_bend_token=left_p.next.tokens[0],
                                           left_border_pid=left_p.next.global_position,
                                           right_bstart_tokens=self.right_bstart_tokens,
                                           right_bend_tokens=self.right_bend_tokens,
                                           right_chapter=self.right_chapter
                                           )
                heapq.heappush(border_matches_heap, border_match)
            except Exception as e:
                logger.exception(f"Error: {e}")
            left_p = left_p.next
        return border_matches_heap

    def spawn_possible(self, thr):
        logger.info(f'Will check if {self} spawn_possible...')
        if not self.border_matches_heap:
            logger.debug('border_matches_heap is empty, spawn_possible is False')
            return False
        # best_border_match = self.border_matches_heap[0]
        logger.debug(f'best_border_match is {self.best_border_match}, thr is {thr}')
        is_spawn_possible = self.best_border_match.border_rate <= thr
        logger.debug(f'spawn_possible is {is_spawn_possible} '
                     f'because best_border_match.border_rate {self.best_border_match.border_rate} <= thr {thr}')
        return is_spawn_possible

    def spawn_child(self, border_rate_threshold):
        logger.info(f'Will spawn_child for {self}...')
        # best_border_match = self.border_matches_heap[0]
        if self.best_border_match.border_rate <= border_rate_threshold:
            parent_left_chapter, child_left_chapter = self.left_chapter.spawn_child(
                self.best_border_match.left_border_pid
            )
            parent_right_chapter, child_right_chapter = self.right_chapter.spawn_child(
                self.best_border_match.best_bend_right_token.paragraph_id
            )

            parent = MatchedChapter(parent_left_chapter, parent_right_chapter,
                                    nbrs=(self.prev, None), born_border_match=self.born_border_match)
            logger.info(f'parent is {parent}')
            child = MatchedChapter(child_left_chapter, child_right_chapter,
                                   nbrs=(parent, self.next), born_border_match=self.best_border_match.border_rate)
            logger.info(f'child is {child}')
            parent.next = child
            if self.prev:
                self.prev.next = parent
            if self.next:
                self.next.prev = child
            return parent, child
        assert "spawn is not possible"


class MatchedChapterByToken(MatchedChapter):
    # def __init__(self, left_chapter: ChapterSide, right_chapter: ChapterSide, nbrs: tuple = (None, None),
    #              born_border_match: float = None):
    #     # combined_text = ' '.join([p.symbols for p in right_chapter.paragraphs.values()])
    #     # paragraph = Paragraph(symbols=combined_text, position=[right_chapter.start_id], nbrs=(None, None))
    #     # right_chapter = ChapterSide(paragraphs={right_chapter.start_id: paragraph},
    #     #                             start_id=right_chapter.start_id,
    #     #                             end_id=right_chapter.start_id)
    #     super().__init__(left_chapter, right_chapter, nbrs, born_border_match)

    def _get_right_tokens(self):
        """
        Fill right_bstart_tokens with tokens that may be in the start of the border - end of current token.
        And right_bend_tokens with tokens that may be in the end of the border - start of next token.
        """
        right_p = self.right_chapter.paragraphs[self.right_chapter.start_id]
        last_right_token_id = right_p.token_borders[-1]
        first_right_token_id = right_p.token_borders[0]

        for (token_start, token_end), token in zip(right_p.token_start_end, right_p.tokens):
            if token_end != last_right_token_id:
                self.right_bstart_tokens[token_start] = token
            if token_start != first_right_token_id:
                self.right_bend_tokens[token_start] = token

    def _fill_border_matches_heap(self):
        border_matches_heap = []
        left_p = self.left_chapter.paragraphs[self.left_chapter.start_id]
        while left_p.global_position < self.left_chapter.end_id:
            try:
                border_match = BorderMatchByToken(left_bstart_token=left_p.tokens[-1],
                                                  left_bend_token=left_p.next.tokens[0],
                                                  left_border_pid=left_p.next.global_position,
                                                  right_bstart_tokens=self.right_bstart_tokens,
                                                  right_bend_tokens=self.right_bend_tokens,
                                                  right_chapter=self.right_chapter
                                                  )
                heapq.heappush(border_matches_heap, border_match)
            except Exception as e:
                print(f"Error: {e}")
            left_p = left_p.next
        return border_matches_heap

    def spawn_child(self, border_rate_threshold):
        best_border_match = self.border_matches_heap[0]
        if best_border_match.border_rate <= border_rate_threshold:

            parent_left_chapter, child_left_chapter = self.left_chapter.spawn_child(
                spawn_global_position=0,
                spawn_local_position=best_border_match.left_border_pid
            )
            parent_right_chapter, child_right_chapter = self.right_chapter.spawn_child(
                spawn_global_position=self.right_chapter.start_id,
                spawn_local_position=best_border_match.best_bend_right_token.paragraph_id
            )

            parent = MatchedChapterByToken(parent_left_chapter, parent_right_chapter,
                                           nbrs=(self.prev, None), born_border_match=self.born_border_match)
            child = MatchedChapterByToken(child_left_chapter, child_right_chapter,
                                          nbrs=(parent, self.next), born_border_match=best_border_match.border_rate)
            parent.next = child
            if self.prev:
                self.prev.next = parent
            if self.next:
                self.next.prev = child
            return parent, child
        assert "spawn is not possible"


class MatchedChapterByBestBorderEndToken(MatchedChapterByToken):

    def _fill_border_matches_heap(self):
        border_matches_heap = []
        left_p = self.left_chapter.paragraphs[self.left_chapter.start_id]
        while left_p.global_position < self.left_chapter.end_id:
            try:
                border_match = BorderMatchByBestBorderEndToken(left_bstart_token=left_p.tokens[-1],
                                                               left_bend_token=left_p.next.tokens[0],
                                                               left_border_pid=left_p.next.global_position,
                                                               right_bstart_tokens=self.right_bstart_tokens,
                                                               right_bend_tokens=self.right_bend_tokens,
                                                               right_chapter=self.right_chapter
                                                               )
                heapq.heappush(border_matches_heap, border_match)
            except Exception as e:
                print(f"Error: {e}")
            left_p = left_p.next
        return border_matches_heap



class MatchedChapterByBestBorderStartToken(MatchedChapterByToken):

    def _fill_border_matches_heap(self):
        border_matches_heap = []
        left_p = self.left_chapter.paragraphs[self.left_chapter.start_id]
        while left_p.global_position < self.left_chapter.end_id:
            try:
                border_match = BorderMatchByBestBorderStartToken(left_bstart_token=left_p.tokens[-1],
                                                                 left_bend_token=left_p.next.tokens[0],
                                                                 left_border_pid=left_p.next.global_position,
                                                                 right_bstart_tokens=self.right_bstart_tokens,
                                                                 right_bend_tokens=self.right_bend_tokens,
                                                                 right_chapter=self.right_chapter
                                                                 )
                heapq.heappush(border_matches_heap, border_match)
            except Exception as e:
                print(f"Error: {e}")
            left_p = left_p.next
        return border_matches_heap




def chapters_by_token_factory(head_chapter):
    prev_chapter_bt = None
    current_chapter = head_chapter

    while current_chapter:
        current_chapter_bt = MatchedChapterByToken(
            left_chapter=current_chapter.left_chapter,
            right_chapter=current_chapter.right_chapter,
            nbrs=(prev_chapter_bt, None)
        )
        if prev_chapter_bt is None:
            head_chapter_bt = current_chapter_bt
        else:
            prev_chapter_bt.next = current_chapter_bt
        prev_chapter_bt = current_chapter_bt
        current_chapter = current_chapter.next

    return head_chapter_bt



def chapters_by_best_be_token_factory(head_chapter):
    prev_chapter_best_bt = None
    current_chapter = head_chapter

    while current_chapter:
        current_chapter_best_bt = MatchedChapterByBestBorderEndToken(
            left_chapter=current_chapter.left_chapter,
            right_chapter=current_chapter.right_chapter,
            nbrs=(prev_chapter_best_bt, None)
        )
        if prev_chapter_best_bt is None:
            head_chapter_bt = current_chapter_best_bt
        else:
            prev_chapter_best_bt.next = current_chapter_best_bt
        prev_chapter_best_bt = current_chapter_best_bt
        current_chapter = current_chapter.next

    return head_chapter_bt



def chapters_by_best_bs_token_factory(head_chapter):
    prev_chapter_best_bt = None
    current_chapter = head_chapter

    while current_chapter:
        current_chapter_best_bt = MatchedChapterByBestBorderStartToken(
            left_chapter=current_chapter.left_chapter,
            right_chapter=current_chapter.right_chapter,
            nbrs=(prev_chapter_best_bt, None)
        )
        if prev_chapter_best_bt is None:
            head_chapter_bt = current_chapter_best_bt
        else:
            prev_chapter_best_bt.next = current_chapter_best_bt
        prev_chapter_best_bt = current_chapter_best_bt
        current_chapter = current_chapter.next

    return head_chapter_bt