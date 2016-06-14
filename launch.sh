RUN_DIR=~/iSDX
RIBS_DIR=$RUN_DIR/xrs/ribs
TEST_DIR=$1
LOG_FILE=SDXLog.log

set -x
# 0 scriptname itself
# 1 example directory (test-mtsim)
# 2 launch part
# 3 no of participants (for launch part 3 only)

case $2 in
    (1)
        if [ ! -d $RIBS_DIR ]
        then
            mkdir $RIBS_DIR
        fi

        cd $RUN_DIR
        sh pctrl/clean.sh

        rm -f $LOG_FILE
        python logServer.py $LOG_FILE
        ;;

    (2)
        # the following gets around issues with vagrant direct mount
        cd ~
        sudo python $RUN_DIR/examples/$TEST_DIR/mininet/simple_sdx.py
#	screen -dmS test2 sudo python $RUN_DIR/examples/$TEST_DIR/mininet/simple_sdx.py

        #cd $RUN_DIR/examples/$TEST_DIR/mininext
        #sudo ./sdx_mininext.py
        ;;

    (3)
        cd $RUN_DIR/flanc
	sleep 1
        sudo ryu-manager ryu.app.ofctl_rest refmon.py --refmon-config $RUN_DIR/examples/$TEST_DIR/config/sdx_global.cfg &
        sleep 3

        cd $RUN_DIR/xctrl
        sudo python xctrl.py $RUN_DIR/examples/$TEST_DIR/config/sdx_global.cfg
	sleep 2

        cd $RUN_DIR/arproxy
        sudo python arproxy.py $TEST_DIR &
        sleep 1

        cd $RUN_DIR/xrs
        sudo python route_server.py $TEST_DIR >> /home/vagrant/routeServer.output 2>&1 &
        sleep 1

        cd $RUN_DIR/pctrl
	for i in $(seq 1 $3); do
		sudo python participant_controller.py $TEST_DIR $i &
	done
#        sudo python participant_controller.py $TEST_DIR 1 &
#        sudo python participant_controller.py $TEST_DIR 2 &
#        sudo python participant_controller.py $TEST_DIR 3 &
#        sudo python participant_controller.py $TEST_DIR 4 &
#        sudo python participant_controller.py $TEST_DIR 5 &
#        sudo python participant_controller.py $TEST_DIR 6 &
#        sudo python participant_controller.py $TEST_DIR 7 &
#        sudo python participant_controller.py $TEST_DIR 8 &
#        sudo python participant_controller.py $TEST_DIR 9 &
#        sudo python participant_controller.py $TEST_DIR 10 &
        sleep 1

#        cd $RUN_DIR
#        exabgp examples/$TEST_DIR/config/bgp.conf
        ;;
esac
