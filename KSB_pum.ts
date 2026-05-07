import { ToastService } from "./../../../../services/toast.service";
import { CommonService } from "app/services/common.service";
import { PubSubService } from "app/services/pub-sub.service";
import { forkJoin } from "rxjs";
import { Params } from "@angular/router";
import { switchMap, map } from "rxjs/operators";
import { ActivatedRoute } from "@angular/router";
import { Observable } from "rxjs/Observable";
import { DevicesService } from "app/services/devices.service";
import { Device } from "app/models/device";
import { Component, OnInit, ViewChild } from "@angular/core";
import { Subscription, EMPTY } from "rxjs";
import * as Highcharts from "highcharts";
import { CalibratedDevice } from "app/utils/calibrate-value";
import { MQTT_DEVICEDATA_TOPIC } from "app/config";
import { IMqttMessage } from "ngx-mqtt";
import { SYSTEM_STATUS, SYSTEM_STATUS1 } from "../ksb-system-status.map";
import * as _ from "lodash";
import * as moment from "moment";
import { DEFAULT_PRESETS2 } from "app/modules/io-lens-widgets-config/iolens-global-timer3-config/gtp-v2-constants";
import { EXPORT_OPTIONS } from "app/utils/io-lens.constants";
import html2canvas from 'html2canvas';
import HC_fullscreen from 'highcharts/modules/full-screen';
import Boost from 'highcharts/modules/boost';
import ExportingModule from 'highcharts/modules/exporting';
import ExportDataModule from 'highcharts/modules/export-data';

ExportDataModule(Highcharts);
ExportingModule(Highcharts);
declare let alasql;
declare let require: any;
require("../../../../../assets/js/core/downsample")(Highcharts);
require("../../../../../assets/js/core/no-data-to-display")(Highcharts);
HC_fullscreen(Highcharts);
Boost(Highcharts);
@Component({
  selector: "ksb-movb",
  templateUrl: "./ksb-movb.component.html",
  styleUrls: ["./ksb-movb.component.scss"],
})
export class KsbMovbComponent implements OnInit {
  // View Child Reference
  @ViewChild("datePicker") datePicker;
  @ViewChild("highChartsRef") highChartsRef: any;

  // Variables
  device: Device;
  pumpCount: number = 2;
  lastDpData: Object = {};
  currentPumps: number[] = [];
  calibrateHelper;
  tableData: any[] = [];
  systemState: string;
  systemStatusKeys = SYSTEM_STATUS;
  systemStatusKeys1 = SYSTEM_STATUS1;
  chartData: any[] = [];
  systemChartData: any;
  exportPumpData: any = {};
  exportSystemData: any = {};
  isDeviceOffline: boolean = true;

  allDurations: any[] = [...DEFAULT_PRESETS2];
  defaultDuration: string = 'Today';
  defaultPeriod: string = 'Daily';
  timeConfig: any = {
    cycleTimeHr: 0,
    cycleTimeMin: 0,
    selectedDate: 1,
    selectedDay: 0,
    selectedMonth: 1
  };
  metrics = {
    systemMetrics: {
      title: ["Pressure Variation With Time", "Energy Consumption Comparison (KT/VT Vs VPT)", "Water Consumption", "Realtime Flow of System"],
    },
    pumpMetrics: {
      title: ["Current Variation With Time", "Frequency Variation With Time", "Active Power Variation with Time", "Pump Status Variation With Time"],
    },
  }
  selectedChartIndex: number = 0;
  ktVTpenergySaved: string;
  isKtAndVtp:boolean = false;
  selectedMetric: string = "systemMetrics";
  exportOptions: { viewValue: string, value: string }[] = EXPORT_OPTIONS;
  startTime: any;
  endTime: any;
  energySaved: number = 0;
  waterConsumed: number = 0;

  // Observables
  devices$: Observable<Device[]>;

  // Subscription
  initSubscription: Subscription;
  lastDpSubscription: Subscription;
  lastDpSubscriptionForWaterAndEnergy: Subscription;
  mqttSubscription: Subscription;
  runTimeHrsSubscription: Subscription;
  chartSubscription: Subscription;

  // HighChart Variables
  HighCharts = Highcharts;
  chartOptions: Object;
  showChartLoader: boolean = true;

  pumpAlarmState: string;
  sensorID:string[] = [];

  timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  private intervalId: any;

  constructor(
    private _devicesService: DevicesService,
    private _route: ActivatedRoute,
    private _pubsub: PubSubService,
    private _commonService: CommonService,
    private _toastService: ToastService
  ) { }

  ngOnInit() {
    // Getting Device Observable
    this.devices$ = this._devicesService.devices$;
    console.log("143", this.devices$);
    // Fetching Device From QueryParam and
    this.initSubscription = this._route.queryParams
      .pipe(
        switchMap((params: Params) => {
          const devID = params.devID;
          return this.devices$.pipe(
            map((devices: Device[]) => {
              return devices.find((device: Device) => device.devID === devID);
            })
          );
        })
      )
      .subscribe((device: any) => {
        console.log("DEVICE : ", device);
        if (device) {
          if (device.properties && device.properties.length) {
            const pumpProperty = device.properties.find((properties: any) => properties.propertyName === "pumpCount");
            // If pumpProperty.propertyValue is greater than or equal to 7,
            // set this.pumpCount to the minimum of 6 and the propertyValue.
            // If pumpProperty.propertyValue is falsy or less than 7, set this.pumpCount to 2.


            if (this.pumpCount === 1) {
              this.pumpCount = 2;
            } else {
              this.pumpCount =  this.pumpCountLogic(pumpProperty.propertyValue);
            }
            const pumpAlarmStateProperty = device.properties.find(
              (properties: any) => properties.propertyName === "pumpAlarmState"
            );
            // If found, assign the propertyValue to this.pumpAlarmState; otherwise, assign a default value newLogic .
            this.pumpAlarmState = pumpAlarmStateProperty ? pumpAlarmStateProperty.propertyValue : "newLogic";
            console.log("PUMP COUNT : ", this.pumpCount, this.pumpAlarmState);
            this.device = device;
            this.getLastDpData();
            this.getLastDPForWaterAndEnergy();
            this.intervalId = setInterval(() => {
              this.getLastDPForWaterAndEnergy();
            }, 60000); // 60000 ms = 1 minute
            this.getRunTime();
            this.subscribeToDevice();
          }
        }
      });
  }

  // Logic to set pumpCount based on the propertyValue
  pumpCountLogic(pumpCount: number) {
    return Number(pumpCount) >= 3
              ? Number(pumpCount) >= 7
                ? 6
                : Number(pumpCount)
              : 2;
  }

  // TO GET LASTDP OF THE SENSORS
  getLastDpData() {
    this.calibrateHelper = new CalibratedDevice(this.device);
    const sensors: string[] = ["RSSI"];
    this.currentPumps = [];
    for (let i = 0; i < this.pumpCount; i++) this.currentPumps.push(i > 2 ? i + 1 : i);
    this.device.sensors.forEach((sensor) => {
      sensors.push(sensor.sensorId);
    });
    this.lastDpSubscription = this._devicesService.getLastDP(this.device.devID, sensors).subscribe((resp: any) => {
      if (resp && resp.data) {     
        this.lastDpData = this.calibrateHelper.calibrateMultiple(resp.data, sensors);
        this.checkSystemState();
      }
      console.log("LAST DP DATA", resp, this.lastDpData);
    });
  }

  // TO GET LASTDP OF THE SENSORS FOR WATER AND ENERGY
  getLastDPForWaterAndEnergy() {
    const devID = this.device.devID;
    // Taking StartTime for RunHours From Device Propertirs
    const startTimeProperty = this.device.properties.find((properties: any) => properties.propertyName === "startTime");
    const startDate = startTimeProperty.propertyValue
      ? moment(startTimeProperty.propertyValue, "DD-MM-YYYY hh:mm:ss").valueOf()
      : moment().subtract("7", "days").unix();
    this.lastDpSubscriptionForWaterAndEnergy = this._devicesService.getLastDPForWaterAndEnergy(devID, startDate).subscribe((resp: any) => {
      if (resp) {
        this.energySaved = isNaN(resp?.energySaved) ? 'N/A' : resp?.energySaved.toFixed(2);
        this.waterConsumed = isNaN(resp?.waterConsumed) ? 'N/A' : resp?.waterConsumed.toFixed(2);
      }
    });
  }

  // SUBSCRIBE TO MQTT FOR LIVE DATA
  subscribeToDevice() {
    const topic = this.device.topic || MQTT_DEVICEDATA_TOPIC.replace("+", this.device.devID);
    this.mqttSubscription = this._pubsub.observe(topic).subscribe((mqttResp: IMqttMessage) => {
      console.log("123", mqttResp.payload.toString());
      const payload = JSON.parse(mqttResp.payload.toString());   
      const formattedData = this._commonService.formatDeviceData(payload.data);
      this.updateDeviceData(formattedData);
    });
  }

  // UPDATING LASTDP DATA
  updateDeviceData(data) {
    console.log("last dp b4 update", this.lastDpData);
    const self = this;
    for (const [sensor, value] of Object.entries(data)) {
      if (self.lastDpData[sensor]) {
        self.lastDpData[sensor].value = self.calibrateHelper.calibrateData(sensor, value);
        self.lastDpData[sensor].time = Date.now();
      }
    }
    this.checkSystemState();
    console.log("Last dp after update", this.lastDpData);
  }

  // TO GET THE PUMP RUN TIME HOURS
  getRunTime() {
    // Taking StartTime for RunHours From Device Propertirs
    const startTimeProperty = this.device.properties.find((properties: any) => properties.propertyName === "startTime");
    const startTime = startTimeProperty.propertyValue
      ? moment(startTimeProperty.propertyValue, "DD-MM-YYYY hh:mm:ss").valueOf()
      : moment().subtract("7", "days").unix();
    const reqOb = {
      startTime,
      endTime: moment().valueOf(),
      devID: this.device.devID,
      sensor: "",
      isconsiderCT: true,
    };
    const userObservables = this.currentPumps.map((pumpID: number, index: number) => {
      return this._devicesService.getDeviceDataDuration({ ...reqOb, sensor: `D${index + 36}` });
    });
    this.runTimeHrsSubscription = forkJoin(userObservables).subscribe((res: any) => {
      console.log("VALUE DURATION : ", res);
      if (res) this.tableData = res;
    });
  }

  /**
   * Checks the system state based on the pump data.
   * Sets the system state to "Active" if any pump has a value of 1,
   * sets it to "N/A" if any pump has a value other than 2,
   * otherwise sets it to "Standby" if all pump values are 2.
   */
  checkSystemState() {
    console.log("PUMP COUNT : ", this.pumpCount, this.pumpAlarmState);
    const logicMapper: any = {
      oldLogic: {
        active: 1,
        standBy: 0,
      },
      newLogic: {
        standBy: 1,
        active: 2,
      },
    };
    var isActive: boolean = false;
    for (let i = 0; i < this.pumpCount; i++) {
      const currentValue = this.lastDpData[`D${this.currentPumps[i] + 8}`]?.value;
      if (currentValue === logicMapper[this.pumpAlarmState].active) {
        isActive = true;
        break;
      }
    }
    this.systemState = isActive ? "Active" : "StandBy";
    this.checkDeviceStatus();
    console.log("SYSTEM STATE", this.systemState);
  }

  // On Date Set
  onDateSet(date) {
    console.log("DATE SET CALLED", date);
    this.chartData = [];
    this.startTime = date.startTime;
    this.endTime = date.endTime;
    this.getChartData(date.startTime, date.endTime);
  }

  getSensorIdbasedOnTitle(title: string): { sensors: string[]; name: string, color: string[] } {
    switch (title) {
      case "Pressure Variation With Time":
        return { sensors: ["D26"], name: "Pressure", color: ['#0E9CFF'] };
      case "Energy Consumption Comparison (KT/VT Vs VPT)":
        this.isKtAndVtp = true;
        return  { sensors: ["D59", "D60"], name: "", color: ['#0E9CFF','#EF8508'] };
      case "Water Consumption":
        return { sensors: ["D58"], name: "Totalizer", color: ['#0E9CFF'] };
      case "Realtime Flow of System":
        return { sensors: ["D57"], name: "Flow", color: ['#0E9CFF'] };
      case "Current Variation With Time":
        return { sensors: this.currentPumps.map((value: number,index:number) => `D${value + 28}`), name: "Pump" ,color: ['#0E9CFF', '#4ACD6F', '#7B61FF', '#EAE337', '#FFB366', '#FF7E6E'] };
      case "Frequency Variation With Time":
        return { sensors: this.currentPumps.map((value: number,index:number) => `D${index + 61}`), name: "Pump" ,color: ['#0E9CFF', '#4ACD6F', '#7B61FF', '#EAE337', '#FFB366', '#FF7E6E'] };
      case "Active Power Variation with Time":
        return { sensors: this.currentPumps.map((value: number,index:number) => `D${index + 45}`), name: "Pump", color: ['#0E9CFF', '#4ACD6F', '#7B61FF', '#EAE337', '#FFB366', '#FF7E6E'] };
      case "Pump Status Variation With Time":
        return { sensors: this.currentPumps.map((value: number,index:number) => `D${value + 8}`), name: "Pump", color: ['#0E9CFF', '#4ACD6F', '#7B61FF', '#EAE337', '#FFB366', '#FF7E6E'] };
      default:
        return { sensors: [], name: "unknown", color: [] };
  }
}

  // GETTING CHART DATA
  getChartData(startTime: any, endTime: any) {
    this.showChartLoader = true;
    const {sensors ,name, color } = this.getSensorIdbasedOnTitle(this.metrics[this.selectedMetric]?.title[this.selectedChartIndex]);
    this.chartSubscription = this._devicesService
      .getKSBChartData(this.device.devID, startTime, endTime, { sensor: sensors })
      .subscribe((resp: any) => {
        if (resp) {
          this.formatChartData(resp, name, color, sensors);
          this.setSelectedChart();
          this.showChartLoader = false;
        }
      });
  }

  formatDataPoints(data: any, name: string, color: string, sensor: string) {

    const currentSeries = {
      name: name,
      data: [],
      color,
      showUnit: this.device.unitSelected[sensor] || '',
      fillColor: {
        linearGradient: {
          x1: 0,
          y1: 0,
          x2: 0,
          y2: 1,
        },
        stops: [
          [0, color],
          [1, new Highcharts.Color(color).setOpacity(0).get("rgba")],
        ],
      },
    };
    if (data && data.length) {
      // Sorting Data in Ascending Order
      data = data.reverse();

      this.exportPumpData[name] = [];
      data.forEach((dataPt) => {
        const time = Date.parse(dataPt.time);

        this.exportPumpData[name].push({
          time: dataPt.time,
          value: dataPt.value ? Number(dataPt.value).toFixed(2) : 0,
          name,
        });
        currentSeries.data.push([time, dataPt.value]);
      });
    }
    console.log("EXPORT DATA", this.exportPumpData);
    return currentSeries;
  }

  // FORMAT CHART DATA
  formatChartData(data: any, name: string, color: string[], sensors: string[]) {
    this.sensorID = sensors;

    if(this.selectedMetric === "systemMetrics") {
      if(this.isKtAndVtp) {
        this.chartData[0] = this.formatDataPoints(data[sensors[0]] || [], 'KT', color[0], sensors[0]);
        this.chartData[1] = this.formatDataPoints(data[sensors[1]] || [], 'VPT', color[1], sensors[1]);
        // Calculating Energy Saved
        const vtpDataPoint = data[sensors[1]][data[sensors[1]].length - 1]?.value - data[sensors[1]][0]?.value;
        const ktDataPoint = data[sensors[0]][data[sensors[0]].length - 1]?.value - data[sensors[0]][0]?.value;
        this.ktVTpenergySaved = isNaN(ktDataPoint - vtpDataPoint) ? "0" : (ktDataPoint - vtpDataPoint).toFixed(2);
      } else {
        this.chartData = [this.formatDataPoints(data[sensors[0]] || [], name, color[0], sensors[0])];
      }
    } else if(this.selectedMetric === "pumpMetrics") {
      for (let i = 0; i < this.pumpCount; i++)
        this.chartData[i] = this.formatDataPoints(data[sensors[i]], `Pump ${i + 1}`, color[i], sensors[i]);
    }
  }
  updateChartTitle(index: number) {
    this.selectedChartIndex = index;
    this.exportPumpData = [];
    this.chartData = [];
    this.isKtAndVtp = false;
    this.getChartData(this.startTime, this.endTime);
  }

  updateMetrics(metric: string) {
    this.selectedMetric = metric;
    this.selectedChartIndex = 0;
    this.exportPumpData = [];
    this.chartData = [];
    this.isKtAndVtp = false;
    this.getChartData(this.startTime, this.endTime);
  }

  handleEvent(value: any) {
    const chart: any = (this.highChartsRef.chart);
    if (chart) {
      if (value == 'fullScreen') {
        chart.fullscreen.toggle();
      }
      else if (['jpeg', 'svg', 'png'].includes(value)) {
        const filename = `${this.metrics[this.selectedMetric]?.title[this.selectedChartIndex] || this.device.devID }-${moment().format("DD-MM-YYYY")}`;

        if (value === 'svg') {
          const svg = chart.getSVG();
          const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = `${filename}.svg`;
          link.click();
          URL.revokeObjectURL(url);
        } else {
          // Use html2canvas for PNG and JPEG
          html2canvas(chart.container).then(canvas => {
            const link = document.createElement('a');
            link.href = canvas.toDataURL(`image/${value}`);
            link.download = `${filename}.${value}`;
            link.click();
          });
        }
      }
      else if (value == 'csv') {
        chart.downloadCSV();
      }
      else if (value == "xls") {
        chart.downloadXLS();
      }
    }
  }

  // Tab Value Setting to Current Chart
  setSelectedChart(){
    // this will convert the data representation of highchart in the local timezone if timezone is undefined then set as Asia/Calcutta
    Highcharts.setOptions({
      time: {
        timezone: this.timezone ? this.timezone :  'Asia/Calcutta'
      }
    });
    this.showChartLoader = true;
    const self = this;
    const currentSeries = [...this.chartData ];

    this.chartOptions = {
      chart: {
        type: "line",
        zoomType: "x",
      },
      title: {
        text: "",
      },
      xAxis: {
        type: "datetime",
      },
      yAxis: {
        title: {
          text: "",
        },
      },
      legend: {
        enabled: true,
      },
      tooltip: {
        formatter: function () {
          return (
            "<b>" +
            this.series.name +
            "</b>
" +
            moment(this.x).format("DD/MM/YYYY @ HH:mm:ss") +
            "
" +
            this.y.toFixed(2) +
            " " + this.series?.userOptions?.showUnit || ''
          );
        },
      },
      plotOptions: {
        area: {
          marker: {
            radius: 2,
          },
          lineWidth: 1,
          states: {
            hover: {
              lineWidth: 1,
            },
          },
          threshold: null,
        },
      },
      credits: {
        enabled: false,
      },
      series: _.cloneDeep(currentSeries),
      exporting: { enabled: false, allowHTML: true },

    };
    this.showChartLoader = false;
  }

  // Function to Check Whether Device is Offline or Online
  checkDeviceStatus() {
    const RSSI = this.lastDpData["RSSI"];
    if (RSSI && RSSI.value) {
      if (RSSI.value !== -1) this.isDeviceOffline = false;
      else {
        // const networkTime = moment(RSSI.time);
        // const timeOut = this.device.properties.find((properties: any) => properties.propertyName === 'connectionTimeout');
        // if (timeOut && moment().diff(networkTime, "seconds") < timeOut.propertyValue)
        //   this.isDeviceOffline = false;
        // else
        this.isDeviceOffline = true;
      }
    } else this.isDeviceOffline = true;
    console.log("RSSSI", RSSI);
  }

  // onDestroy Unsubscribing to all Subscriptions
  ngOnDestroy(): void {
    //Called once, before the instance is destroyed.
    //Add 'implements OnDestroy' to the class.
    if (this.initSubscription) this.initSubscription.unsubscribe();
    if (this.mqttSubscription) this.mqttSubscription.unsubscribe();
    if (this.lastDpSubscription) this.lastDpSubscription.unsubscribe();
    if (this.lastDpSubscriptionForWaterAndEnergy) this.lastDpSubscriptionForWaterAndEnergy.unsubscribe();
    if (this.chartSubscription) this.chartSubscription.unsubscribe();
    if (this.runTimeHrsSubscription) this.runTimeHrsSubscription.unsubscribe();
    if (this.intervalId) {
      clearInterval(this.intervalId);
    }
  }
}
 