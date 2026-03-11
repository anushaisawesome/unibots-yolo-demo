state = 'SEARCHING'

while True:
    if state                                                                           == 'SEARCHING':
       search_behavior()
    elif state == 'APPROACHING':
       approach_behavior()
    elif state == 'COLLECTING':
       collect_behavior()
    elif state == 'RETURNING_HOME':
       return_home_behavior()
    elif state == 'DROPPING':
       drop_behavior()
   
    if ball_detected:
        state = 'APPROACHING'
    if close_to_ball:
        state = 'COLLECTING'
    if ball_count >= MAX_CAPACITY:
        state = 'RETURNING_HOME'
    if at_home:
        state = 'DROPPING'
    if dropped:
        state = 'SEARCHING'

