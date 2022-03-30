from curses import wrapper, curs_set, init_pair, COLOR_BLACK, COLOR_WHITE, newwin, A_UNDERLINE, color_pair, KEY_LEFT, \
    KEY_RIGHT, KEY_RESIZE, KEY_ENTER, doupdate
from _curses import window
from loguru import logger
from threading import Thread, Event
from time import sleep

current_item = 0
menu_change_flag = False

menu_frames = 0
info_frames = 0

resize_flag = False

tui_refresh_out = Event()


@logger.catch()
def start_tui_init(std_scr, menu_items):
    global current_item

    curs_set(0)  # Cursor - 0,1,2 (without/underline/rectangle)
    init_pair(1, COLOR_BLACK, COLOR_WHITE)  # Change color pair
    std_scr.refresh()
    max_y, max_x = std_scr.getmaxyx()
    menu_win = newwin(3, max_x, 0, 0)
    menu_win.box()
    menu_win.addstr(0, 1, f'Proxy Provider RC1 {max_y=} {max_x=} frame 0')
    x, y = 1, 1
    menu_win.attron(A_UNDERLINE)

    for idx, row in enumerate(menu_items):
        item_len = len(row)
        if idx == current_item:
            menu_win.attron(color_pair(1))
            menu_win.addstr(y, x, row)
            menu_win.attroff(color_pair(1))
        else:
            menu_win.addstr(y, x, row)
        x = x + item_len + 1

    menu_win.attroff(A_UNDERLINE)
    info_win = newwin(max_y - 3, max_x, 3, 0)
    info_win.box()
    info_win.refresh()
    menu_win.refresh()
    return menu_win, info_win


@logger.catch()
def tui(std_scr, menu_win: window, info_win: window, sm_dict_for_buffers, sm_dict_for_change_flags, menu_items):
    global menu_change_flag, current_item, resize_flag, menu_frames, info_frames
    max_y, max_x = std_scr.getmaxyx()

    if resize_flag:
        resize_flag = False
        menu_win.resize(3, max_x)
        info_win.resize(max_y - 3, max_x)
        menu_change_flag = True
        sm_dict_for_change_flags[menu_items[current_item]].value = True
    if menu_change_flag:
        menu_change_flag = False
        menu_frames += 1
        menu_win.clear()
        menu_win.box()
        menu_win.addstr(0, 1, f'Proxy Provider RC1 {max_y=} {max_x=} frame {menu_frames}')

        x, y = 1, 1
        menu_win.attron(A_UNDERLINE)

        for idx, row in enumerate(menu_items):
            item_len = len(row)

            if idx == current_item:
                menu_win.attron(color_pair(1))
                menu_win.addstr(y, x, row)
                menu_win.attroff(color_pair(1))
            else:
                menu_win.addstr(y, x, row)

            x = x + item_len + 1
        menu_win.attroff(A_UNDERLINE)
        menu_win.noutrefresh()
        sm_dict_for_change_flags[menu_items[current_item]].value = True
    if sm_dict_for_change_flags[menu_items[current_item]].value:
        sm_dict_for_change_flags[menu_items[current_item]].value = False
        iw_m_y, iw_m_x = info_win.getmaxyx()
        info_frames += 1
        max_y, max_x = std_scr.getmaxyx()
        info_win.clear()
        info_win.box()
        info_win.addstr(0, 1, f'{info_frames}')
        info_win.addstr(0, 5, f'{iw_m_y=} {iw_m_x=} {max_y=} {max_x=}')
        screen_buffer = sm_dict_for_buffers[menu_items[current_item]]
        if screen_buffer:
            free_zone_start = 1
            screen_buffer_y_size, screen_buffer_x_size = iw_m_y - 2, iw_m_x - 2
            if menu_items[current_item] == 'Proxy Tester':
                max_len_str = 0
                for str_in_buffer in screen_buffer:
                    if len(str_in_buffer) + 1 > max_len_str:
                        max_len_str = len(str_in_buffer) + 1
                num_columns = int(screen_buffer_x_size / max_len_str)
                if num_columns > 1:
                    new_buffer = []
                    new_str_data = ''
                    cur_num_col = 0
                    size_screen_buffer = len(screen_buffer)
                    for num, str_data in enumerate(screen_buffer):
                        new_str_data = new_str_data + f'{str_data:<{max_len_str}}'
                        cur_num_col += 1
                        if cur_num_col == num_columns:
                            new_buffer.append(new_str_data)
                            new_str_data = ''
                            cur_num_col = 0
                            continue
                        if num == size_screen_buffer - 1 and cur_num_col != num_columns:
                            new_buffer.append(new_str_data)
                    screen_buffer = new_buffer
                if len(screen_buffer) > screen_buffer_y_size:
                    screen_buffer = screen_buffer[-screen_buffer_y_size:]
                for num, str_data in enumerate(screen_buffer):
                    if len(str_data) > screen_buffer_x_size:
                        str_data = str_data[-screen_buffer_x_size:]
                    info_win.addstr(free_zone_start + num, 1, str_data)
            else:
                if len(screen_buffer) > screen_buffer_y_size:
                    screen_buffer = screen_buffer[-screen_buffer_y_size:]
                for num, str_data in enumerate(screen_buffer):
                    if len(str_data) > screen_buffer_x_size:
                        str_data = str_data[-screen_buffer_x_size:]
                    info_win.addstr(free_zone_start + num, 1, str_data)
        info_win.noutrefresh()
    doupdate()


@logger.catch()
def tue_event_loop(
        std_scr, sm_p_status, sm_tui_refresh, menu_win, info_win, sm_dict_for_buffers, sm_dict_for_change_flags,
        menu_items
):
    global tui_refresh_out
    while sm_p_status.value:
        tui(std_scr, menu_win, info_win, sm_dict_for_buffers, sm_dict_for_change_flags, menu_items)
        tui_refresh_out.set()
        sm_tui_refresh.wait()
        sm_tui_refresh.clear()


@logger.catch()
def main(
        std_scr, sm_p_status, sm_dict_for_buffers, sm_dict_for_change_flags, sm_tui_refresh, menu_items, rest_api_p,
        sm_p_id_list, sm_timer_event
):
    global current_item, menu_change_flag, resize_flag, info_frames, tui_refresh_out
    menu_win, info_win = start_tui_init(std_scr, menu_items)

    t = Thread(target=tue_event_loop, args=(
        std_scr, sm_p_status, sm_tui_refresh, menu_win, info_win, sm_dict_for_buffers, sm_dict_for_change_flags,
        menu_items
    ))
    t.start()

    while sm_p_status.value:
        key = std_scr.getch()
        if key == KEY_LEFT and current_item > 0:
            current_item -= 1
            menu_change_flag = True
        elif key == KEY_RIGHT and current_item < len(menu_items) - 1:
            current_item += 1
            menu_change_flag = True
        elif key == KEY_RESIZE:
            resize_flag = True
        elif key in (KEY_ENTER, 10, 13) and current_item == len(menu_items) - 1:
            sm_p_status.value = False
            rest_api_p.terminate()
            sm_timer_event.set()
            while True:
                info_frames += 1
                info_win.clear()
                info_win.box()
                info_win.addstr(0, 1, f'{info_frames}')
                info_win.addstr(1, 1, f'Wait {len(list(sm_p_id_list))} processes')
                if len(sm_p_id_list) != 0:
                    for num, process_wait in enumerate(list(sm_p_id_list)):
                        info_win.addstr(2 + num, 1, f'Wait "{process_wait}" processes')
                    info_win.refresh()
                    sleep(0.5)
                else:
                    sm_tui_refresh.set()
                    break
        sm_tui_refresh.set()
        tui_refresh_out.wait()
        tui_refresh_out.clear()

    t.join()


@logger.catch()
def curses_tui(
        sm_p_status, sm_dict_for_buffers, sm_dict_for_change_flags, sm_tui_refresh, menu_items, rest_api_p,
        sm_p_id_list, sm_timer_event
):
    wrapper(
        main, sm_p_status, sm_dict_for_buffers, sm_dict_for_change_flags, sm_tui_refresh, menu_items, rest_api_p,
        sm_p_id_list, sm_timer_event
    )
