#!/bin/bash

case $HOSTNAME in
	(mkubica)
		sudo cp error_catcher.service controller.service inverter.service /etc/systemd/system 
		sudo systemctl daemon-reload
		sudo systemctl restart error_catcher.service
		sudo systemctl restart controller.service
		sudo systemctl restart inverter.service
		;;
	(outsider)
		sudo cp main_energy_meter.service house_energy_meter.service /etc/systemd/system
		sudo systemctl daemon-reload
		sudo systemctl restart main_energy_meter.service
		sudo systemctl restart house_energy_meter.service
		;;

  	(choreman) 
  		sudo cp hp_energy_meter.service /etc/systemd/system
  		sudo systemctl daemon-reload
  		sudo systemctl restart hp_energy_meter.service
  		;;
esac
