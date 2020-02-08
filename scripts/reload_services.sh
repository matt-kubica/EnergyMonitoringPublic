#!/bin/bash

sudo systemctl daemon-reload
case $HOSTNAME in
	(mkubica)
		sudo systemctl restart error_catcher.service
		sudo systemctl restart controller.service
		sudo systemctl restart inverter.service
		;;
	(outsider)
		sudo systemctl restart main_energy_meter.service
		sudo systemctl restart house_energy_meter.service
		;;
  	(choreman) 
  		sudo systemctl restart hp_energy_meter.service
  		;;
esac