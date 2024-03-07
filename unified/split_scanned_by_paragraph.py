from unified.paragraph import paragraph_factory, chapters_by_token_factory, MatchedChapter, ChapterSide, logger
from unified.paragraph import chapters_by_best_be_token_factory, chapters_by_best_bs_token_factory
from typing import List
import heapq as hq
# logger = logging.getLogger(__name__)


class ReasonableThreshold(object):
    def __init__(self, chapter: MatchedChapter):
        self.chapter = chapter
        self.reasonable_thr = chapter.best_border_match.border_rate if chapter.best_border_match else None

    def __lt__(self, other):
        return self.reasonable_thr < other.reasonable_thr

    def __repr__(self):
        return f"X({self.reasonable_thr} for MatchedChapter {self.chapter})"


def write_chapters_to_files(head_chapter, filename_prefix, thr):
    text_left = ''
    text_right = ''
    with open(f'{filename_prefix}_left_{thr}.txt', 'w') as f_left:
        with open(f'{filename_prefix}_right_{thr}.txt', 'w') as f_right:
            write_chapter = head_chapter
            while write_chapter:
                header_to_write = f"se2_id: {write_chapter.se2_id}, born_border_match: " \
                                  f"{write_chapter.born_border_match}, timestamp: {write_chapter.born_datetime}\n"
                f_left.write(header_to_write)
                f_right.write(header_to_write)

                lines_to_write = ''
                for key, val in write_chapter.left_chapter.paragraphs.items():
                    if key >= write_chapter.left_chapter.start_id and key <= write_chapter.left_chapter.end_id:
                        lines_to_write += val.symbols
                f_left.writelines(lines_to_write)
                text_left += lines_to_write
                text_left += '\n'

                lines_to_write = ''
                for key, val in write_chapter.right_chapter.paragraphs.items():
                    if key >= write_chapter.right_chapter.start_id and key <= write_chapter.right_chapter.end_id:
                        lines_to_write += val.symbols
                f_right.writelines(lines_to_write)
                text_right += lines_to_write
                text_right += '\n'

                write_chapter = write_chapter.next
    return text_left, text_right


def reasonable_threshold_fabric(head_chapter: MatchedChapter, thr):
    current_chapter = head_chapter
    while current_chapter:
        rt = ReasonableThreshold(current_chapter)
        if rt.reasonable_thr is not None and rt.reasonable_thr <= thr:
            yield rt
        current_chapter = current_chapter.next

def spawn_chapters(head_chapter: MatchedChapter, thr):
    # next_chapter = head_chapter
    next_reasonable_thr_heap = list(reasonable_threshold_fabric(head_chapter, thr))
    hq.heapify(next_reasonable_thr_heap)
    while (next_reasonable_thr_heap and
           next_reasonable_thr_heap[0].reasonable_thr is not None and
           next_reasonable_thr_heap[0].reasonable_thr <= thr):
        current_chapter = hq.heappop(next_reasonable_thr_heap).chapter
        # next_chapter = next_chapter.next
        logger.info(f'current_chapter is {current_chapter}')
        # TODO: speedup  current_chapter.spawn_child
        # TODO: multiprocessing workers for current_chapter.spawn_child - check structures to lock against race
        parent_chapter, child_chapter = current_chapter.spawn_child(thr)
        current_chapter.is_obsolete = True
        # all_m_chapters[parent_chapter.se2_id] = parent_chapter
        # all_m_chapters[child_chapter.se2_id] = child_chapter

        if current_chapter is head_chapter:
            head_chapter = parent_chapter
        # current_chapter = child_chapter

        if parent_chapter.best_border_match:
            hq.heappush(next_reasonable_thr_heap, ReasonableThreshold(parent_chapter))
        if child_chapter.best_border_match:
            hq.heappush(next_reasonable_thr_heap, ReasonableThreshold(child_chapter))
    return head_chapter


def flatten_right_paragraphs_text(head_chapter):
    right_text = ''
    next_chapter = head_chapter
    right_text_by_lines = []

    while next_chapter:
        right_paragraphs = next_chapter.right_chapter.paragraphs
        for pid in right_paragraphs.keys():
            current_paragraph_text = right_paragraphs[pid].symbols
            right_text += current_paragraph_text.replace('\n', ' ')
            if next_chapter and pid == next_chapter.right_chapter.end_id:
                # right_text.replace('\n', '')
                right_text += '\n' if right_text else ''
                right_text_by_lines.append(right_text)
                right_text = ''
                next_chapter = next_chapter.next
    # right_text_by_lines.append('\n')
    return right_text_by_lines


def match_chapter_1(left_chapter, right_chapter, max_thr):
    logger.info('MatchedChapter - 1st iteration')
    head_chapter = MatchedChapter(left_chapter, right_chapter)
    logger.info(f'Next thr cycle started.! thr is {max_thr}')
    head_chapter = spawn_chapters(head_chapter, max_thr)
    return head_chapter


def match_chapter_2(left_chapter, head_chapter, max_thr):
    logger.info('flatten_right_paragraphs_text...')
    right_text = flatten_right_paragraphs_text(head_chapter)
    # Build data structeres from the scratch
    right_paragraphs = paragraph_factory(right_text)
    right_chapter = ChapterSide(right_paragraphs, 0, next(reversed(right_paragraphs)))
    head_chapter = MatchedChapter(left_chapter, right_chapter)

    #       2. run MatchedChapter spawn_subchapter cycle once again
    logger.info('MatchedChapter - 2nd iteration')
    head_chapter = spawn_chapters(head_chapter, max_thr)

    return head_chapter


def match_chapter_bt(head_chapter, max_thr):
    logger.info('chapters_by_token_factory...')
    head_chapter_bt = chapters_by_token_factory(head_chapter)

    logger.info('MatchedChapterByToken iteration')

    head_chapter_bt = spawn_chapters(head_chapter_bt, max_thr)
    left_final, right_final = write_chapters_to_files(head_chapter_bt, 'bt_thr', max_thr)
    a = 1
    return left_final, right_final, head_chapter_bt


def match_chapter_be_bt(head_chapter_bt, max_thr):
    logger.info('chapters_by_best_be_token_factory...')
    head_chapter_best_be_bt = chapters_by_best_be_token_factory(head_chapter_bt)
    # logger.info('MatchedChapterByBestToken iteration')

    head_chapter_best_be_bt = spawn_chapters(head_chapter_best_be_bt, max_thr)
    left_final, right_final = write_chapters_to_files(head_chapter_best_be_bt, 'best_be_bt_thr', max_thr)

    return left_final, right_final, head_chapter_best_be_bt


def match_chapter_bs_bt(head_chapter_bt, max_thr):
    logger.info('chapters_by_best_be_token_factory...')
    head_chapter_best = chapters_by_best_bs_token_factory(head_chapter_bt)
    # logger.info('MatchedChapterByBestToken iteration')
    head_chapter_best = spawn_chapters(head_chapter_best, max_thr)
    left_final, right_final = write_chapters_to_files(head_chapter_best, 'best_be_bt_thr', max_thr)

    return left_final, right_final, head_chapter_best


def main(source_left: List[str], source_right: List[str], max_thr):
    left_paragraphs = paragraph_factory(source_left)
    right_paragraphs = paragraph_factory(source_right)

    left_chapter = ChapterSide(left_paragraphs, 0, next(reversed(left_paragraphs)))
    right_chapter = ChapterSide(right_paragraphs, 0, next(reversed(right_paragraphs)))

    head_chapter = match_chapter_1(left_chapter, right_chapter, max_thr)
    head_chapter = match_chapter_2(left_chapter, head_chapter, max_thr)
    left_final, right_final, head_chapter_bt = match_chapter_bt(head_chapter, max_thr)
    left_final, right_final, head_chapter_be_bt = match_chapter_be_bt(head_chapter_bt, max_thr)
    left_final, right_final, head_chapter_bs_bt = match_chapter_be_bt(head_chapter_be_bt, max_thr)

    return left_final, right_final


if __name__ == '__main__':
    with open('left_mondi_short.txt') as f:
        left_text_ = f.readlines()
    with open('right_mondi_short.txt') as f:
        right_text_ = f.readlines()

    max_thr_ = 200

    left_final_, right_final_ = main(left_text_, right_text_, max_thr_)

    with open('output_left_final.txt', 'w') as f_left:
        f_left.write(left_final_)

    with open('output_right_final.txt', 'w') as f_right:
        f_right.write(right_final_)

    points = len(left_final_.split('\n\n'))
    logger.info(f"points={points}")