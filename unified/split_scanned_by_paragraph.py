from unified.paragraph import paragraph_factory, chapters_by_token_factory, MatchedChapter, ChapterSide, logger
from unified.paragraph import chapters_by_best_be_token_factory, chapters_by_best_bs_token_factory
from typing import List
# logger = logging.getLogger(__name__)


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


def spawn_chapters(head_chapter: MatchedChapter, thr):
    next_chapter = head_chapter
    while next_chapter:
        current_chapter = next_chapter
        next_chapter = next_chapter.next
        while current_chapter.spawn_possible(thr):
            logger.info(f'current_chapter is {current_chapter}')
            parent_chapter, child_chapter = current_chapter.spawn_child(thr)
            current_chapter.is_obsolete = True
            # all_m_chapters[parent_chapter.se2_id] = parent_chapter
            # all_m_chapters[child_chapter.se2_id] = child_chapter

            if current_chapter is head_chapter:
                head_chapter = parent_chapter
            current_chapter = child_chapter
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
    thr = .1
    while thr < max_thr:
        logger.info(f'Next thr cycle started.! thr is {thr}')
        head_chapter = spawn_chapters(head_chapter, thr)
        # write_chapters_to_files(head_chapter, 'thr', thr)

        thr *= 1 + 0.618
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
    thr = .1
    while thr < max_thr:
        head_chapter = spawn_chapters(head_chapter, thr)
        # write_chapters_to_files(head_chapter, 'thr2', thr)
        thr *= 1 + 0.618

    return head_chapter


def match_chapter_bt(head_chapter, max_thr):
    logger.info('chapters_by_token_factory...')
    head_chapter_bt = chapters_by_token_factory(head_chapter)

    logger.info('MatchedChapterByToken iteration')
    thr = .1
    while thr < max_thr * pow(0.618, 1):
        head_chapter_bt = spawn_chapters(head_chapter_bt, thr)
        left_final, right_final = write_chapters_to_files(head_chapter_bt, 'bt_thr', thr)

        thr *= 1 + 0.618
        print(thr)
    a = 1
    return left_final, right_final, head_chapter_bt


def match_chapter_be_bt(head_chapter_bt, max_thr):
    logger.info('chapters_by_best_be_token_factory...')
    head_chapter_best_be_bt = chapters_by_best_be_token_factory(head_chapter_bt)
    # logger.info('MatchedChapterByBestToken iteration')
    thr = .1
    while thr < max_thr * pow(0.618, 8):  # 15 mean run only once
        head_chapter_best_be_bt = spawn_chapters(head_chapter_best_be_bt, thr)
        left_final, right_final = write_chapters_to_files(head_chapter_best_be_bt, 'best_be_bt_thr', thr)

        thr *= 1 + 0.618
        print(thr)

    return left_final, right_final, head_chapter_best_be_bt


def match_chapter_bs_bt(head_chapter_bt, max_thr):
    logger.info('chapters_by_best_be_token_factory...')
    head_chapter_best = chapters_by_best_bs_token_factory(head_chapter_bt)
    # logger.info('MatchedChapterByBestToken iteration')
    thr = .1
    while thr < max_thr * pow(0.618, 8):  # 15 mean run only once
        head_chapter_best = spawn_chapters(head_chapter_best, thr)
        left_final, right_final = write_chapters_to_files(head_chapter_best, 'best_be_bt_thr', thr)

        thr *= 1 + 0.618
        print(thr)

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
    with open('left.txt') as f:
        left_text_ = f.readlines()
    with open('right.txt') as f:
        right_text_ = f.readlines()

    max_thr_ = 200

    left_final_, right_final_ = main(left_text_, right_text_, max_thr_)

    with open('output_left_final.txt', 'w') as f_left:
        f_left.write(left_final_)

    with open('output_right_final.txt', 'w') as f_right:
        f_right.write(right_final_)